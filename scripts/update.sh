#!/usr/bin/env bash
# Keeps the workspace up to date (ADR-0023). Fetches every workspace repository, fast-forwards `main`
# where it is checked out without local changes, and clones new organization repositories. Everything
# that needs a decision is only reported, in $UPDATE_REPORT_FILE. Run every 10 minutes by a systemd
# user timer (scripts/configure-updates.sh), and by `mise run update`.
source "$(dirname "$0")/lib.sh"

# One run at a time: a run that finds another one in progress leaves it to finish.
mkdir -p "$(dirname "$UPDATE_LOCK_FILE")"
exec 9>"$UPDATE_LOCK_FILE"
flock -n 9 || { info "Another update is running"; exit 0; }

report=()
note() { report+=("$*"); }

# Prints why git must not be touched now, if a git operation is in progress.
busy() {
  local git_dir
  git_dir="$(git -C "$1" rev-parse --git-dir)"
  [[ "$git_dir" == /* ]] || git_dir="$1/$git_dir"
  [[ -e "$git_dir/index.lock" || -d "$git_dir/rebase-merge" || -d "$git_dir/rebase-apply" ||
     -e "$git_dir/MERGE_HEAD" || -e "$git_dir/CHERRY_PICK_HEAD" ]]
}

# A changed or newly cloned playbook is installed again, so its commands and skills stay current.
reinstall_playbook() {
  if ! command -v mise >/dev/null && ! command -v uv >/dev/null; then
    note "playbook: changed, but not installed again: it needs mise; run workbench/scripts/install-playbook.sh once mise is installed"
  elif "$REPOSITORY_DIR/scripts/install-playbook.sh" >/dev/null 2>&1; then
    note "playbook: installed again"
  else
    note "playbook: could not be installed again; run workbench/scripts/install-playbook.sh"
  fi
}

update_repository() {
  local directory="$1" name branch behind ahead
  name="$(basename "$directory")"
  if busy "$directory"; then
    note "$name: skipped, a git operation is in progress"
    return
  fi
  if ! git -C "$directory" fetch --quiet --prune origin 2>/dev/null; then
    note "$name: could not fetch from GitHub; check the sign-in with scripts/doctor.sh"
    return
  fi
  git -C "$directory" rev-parse --verify --quiet origin/main >/dev/null || return 0
  branch="$(git -C "$directory" symbolic-ref --short --quiet HEAD || true)"

  if [[ "$branch" == main ]]; then
    behind="$(git -C "$directory" rev-list --count main..origin/main)"
    ahead="$(git -C "$directory" rev-list --count origin/main..main)"
    if ((ahead > 0)); then
      note "$name: main has $ahead commit(s) that are not on GitHub; move them to a branch"
    elif ((behind > 0)); then
      if [[ -n "$(git -C "$directory" status --porcelain --untracked-files=no)" ]]; then
        note "$name: $behind new commit(s) on main, not applied: there are local changes"
      elif git -C "$directory" merge --ff-only --quiet origin/main 2>/dev/null; then
        note "$name: updated, $behind new commit(s)"
        if [[ "$name" == workbench ]]; then
          note "workbench changed: run workbench/setup.sh to apply it"
        fi
        if [[ "$name" == playbook ]]; then
          reinstall_playbook
        fi
      else
        note "$name: $behind new commit(s) on main, not applied: git refused to fast-forward"
      fi
    fi
  elif [[ -n "$branch" ]]; then
    if [[ -n "$(git -C "$directory" config "branch.$branch.remote")" ]] &&
      ! git -C "$directory" rev-parse --verify --quiet "origin/$branch" >/dev/null; then
      note "$name: $branch was merged or deleted on GitHub; switch to main and delete it"
    fi
    behind="$(git -C "$directory" rev-list --count HEAD..origin/main)"
    if ((behind > 0)); then
      note "$name: $branch is $behind commit(s) behind main"
    fi
  fi
}

for directory in "$WORKSPACE_DIR"/* "$WORKSPACE_DIR"/.[!.]*; do
  if [[ -d "$directory/.git" ]]; then
    update_repository "$directory"
  fi
done

# New repositories, and the workspace files that list them.
if cloned="$("$REPOSITORY_DIR/scripts/clone-repositories.sh" 2>/dev/null)"; then
  new="$(sed -n 's/^.* \(.*\) (cloned)$/\1/p' <<<"$cloned" | paste -sd, - | sed 's/,/, /g')"
  if [[ -n "$new" ]]; then
    note "cloned new repositories: $new"
    "$REPOSITORY_DIR/scripts/write-workspace-files.sh" >/dev/null
    if [[ ", $new, " == *", playbook, "* ]]; then
      reinstall_playbook
    fi
  fi
else
  note "could not list the organization's repositories; check the sign-in with scripts/doctor.sh"
fi

{
  echo "# Workspace update, $(date '+%Y-%m-%d %H:%M')"
  if ((${#report[@]} == 0)); then
    echo "Everything is up to date."
  else
    printf -- '- %s\n' "${report[@]}"
  fi
} >"$UPDATE_REPORT_FILE"
cat "$UPDATE_REPORT_FILE"
