#!/usr/bin/env bash
# Tests scripts/update.sh in a throwaway workspace, against local bare repositories, with a stand-in for
# gh that lists and clones them. Needs Python 3 with PyYAML, like setup.
set -euo pipefail

repository_dir="$(cd "$(dirname "$0")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
export HOME="$work/home" BYTELIBRARY_WORKSPACE_DIR="$work/ByteLibrary" BYTELIBRARY_UPDATE_LOCK_FILE="$work/update.lock"
export GIT_CONFIG_GLOBAL="$work/home/.gitconfig" REMOTES="$work/remotes" FAKE_REPOSITORIES="alpha beta gamma delta epsilon"
mkdir -p "$HOME" "$REMOTES" "$BYTELIBRARY_WORKSPACE_DIR" "$work/bin"
git config --global user.name Test && git config --global user.email test@example.com
git config --global init.defaultBranch main

cat >"$work/bin/gh" <<'GH'
#!/usr/bin/env bash
# Stands in for gh: lists the test's repositories and clones them from the local bare repositories.
case "$1" in
  api) printf '%s\n' $FAKE_REPOSITORIES ;;
  repo) git clone --quiet "$REMOTES/${3#*/}.git" "$4" ;;
esac
GH
chmod +x "$work/bin/gh"
# Stands in for uv, so the playbook's installer can run without mise.
printf '#!/usr/bin/env bash\nexit 0\n' >"$work/bin/uv" && chmod +x "$work/bin/uv"
export PATH="$work/bin:$PATH"

# A remote with one commit, and a clone of it in the workspace (unless it is new).
remote() {
  git init --quiet --bare "$REMOTES/$1.git"
  git clone --quiet "$REMOTES/$1.git" "$work/seed-$1" 2>/dev/null
  echo "$1" >"$work/seed-$1/README.md"
  if [[ "$1" == playbook ]]; then
    # Stands in for the playbook's installer: records each run.
    printf '#!/usr/bin/env bash\necho run >>"%s/playbook-installs"\n' "$work" >"$work/seed-$1/install.sh"
    chmod +x "$work/seed-$1/install.sh"
  fi
  if [[ "$1" == handbook ]]; then
    mkdir -p "$work/seed-$1/data"
    printf -- '- code: tooling\n  description: Tools\n' >"$work/seed-$1/data/repository-kinds.yaml"
  fi
  git -C "$work/seed-$1" add -A && git -C "$work/seed-$1" commit --quiet -m "chore: start"
  git -C "$work/seed-$1" push --quiet origin main
  [[ "${2:-}" == new ]] || git clone --quiet "$REMOTES/$1.git" "$BYTELIBRARY_WORKSPACE_DIR/$1"
}
# A new commit on the remote's main.
advance() {
  echo "change" >>"$work/seed-$1/README.md"
  git -C "$work/seed-$1" commit --quiet -am "docs: change"
  git -C "$work/seed-$1" push --quiet origin main
}

for name in handbook alpha beta gamma delta playbook; do remote "$name"; done
remote epsilon new

# alpha: main, clean, behind. beta: main with local changes, behind. gamma: a branch whose pull request
# was merged, behind main. delta: a git operation in progress.
advance alpha
advance playbook
advance beta && echo "local" >>"$BYTELIBRARY_WORKSPACE_DIR/beta/README.md"
git -C "$BYTELIBRARY_WORKSPACE_DIR/gamma" switch --quiet -c feat/1-example
git -C "$BYTELIBRARY_WORKSPACE_DIR/gamma" push --quiet -u origin feat/1-example 2>/dev/null
git -C "$work/seed-gamma" push --quiet origin --delete feat/1-example 2>/dev/null || git --git-dir="$REMOTES/gamma.git" branch -D feat/1-example >/dev/null
advance gamma
advance delta && touch "$BYTELIBRARY_WORKSPACE_DIR/delta/.git/index.lock"

report="$("$repository_dir/scripts/update.sh" 2>&1)"

failures=0
expect() {
  local description="$1"
  shift
  if "$@" >/dev/null 2>&1; then echo "ok   $description"; else echo "FAIL $description"; failures=$((failures + 1)); fi
}
on_origin_main() { [[ "$(git -C "$BYTELIBRARY_WORKSPACE_DIR/$1" rev-parse HEAD)" == "$(git -C "$BYTELIBRARY_WORKSPACE_DIR/$1" rev-parse origin/main)" ]]; }
behind_origin_main() { ! on_origin_main "$1"; }
reports() { grep -qF "$1" <<<"$report"; }

expect "a clean main is fast-forwarded" on_origin_main alpha
expect "... and reported" reports "alpha: updated, 1 new commit(s)"
expect "a main with local changes is left alone" behind_origin_main beta
expect "... its local change is kept" grep -q local "$BYTELIBRARY_WORKSPACE_DIR/beta/README.md"
expect "... and reported" reports "beta: 1 new commit(s) on main, not applied: there are local changes"
expect "a branch is never switched" test "$(git -C "$BYTELIBRARY_WORKSPACE_DIR/gamma" branch --show-current)" = feat/1-example
expect "... a merged branch is reported" reports "gamma: feat/1-example was merged or deleted on GitHub"
expect "... a branch behind main is reported" reports "gamma: feat/1-example is 1 commit(s) behind main"
expect "a repository with a git operation in progress is skipped" reports "delta: skipped, a git operation is in progress"
expect "a new repository is cloned" test -d "$BYTELIBRARY_WORKSPACE_DIR/epsilon/.git"
expect "... reported" reports "cloned new repositories: epsilon"
expect "... and added to the workspace files" grep -q epsilon "$BYTELIBRARY_WORKSPACE_DIR/ByteLibrary.code-workspace"
expect "a changed playbook is installed again" test -s "$work/playbook-installs"
expect "... and reported" reports "playbook: installed again"
expect "the report is written for agents" grep -qF "alpha: updated" "$BYTELIBRARY_WORKSPACE_DIR/.workspace-update.md"

second="$("$repository_dir/scripts/update.sh" 2>&1)"
expect "a second run has nothing new for alpha" bash -c '! grep -q "alpha:" <<<"$1"' _ "$second"

exec 8>"$BYTELIBRARY_UPDATE_LOCK_FILE" && flock 8
expect "a run stops while another one runs" bash -c "'$repository_dir/scripts/update.sh' | grep -q 'Another update is running'"
exec 8>&-

if ((failures > 0)); then
  echo "$failures test(s) failed"
  exit 1
fi
echo "all tests passed"
