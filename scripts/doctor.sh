#!/usr/bin/env bash
# Checks that the workspace is set up correctly. Safe to run at any time.
source "$(dirname "$0")/lib.sh"

failures=0
check() {
  local description="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    ok "$description"
  else
    warn "$description"
    failures=$((failures + 1))
  fi
}

gh_logged_in() { gh_scoped auth status --hostname github.com; }

token_limited_to_organization() {
  local outside
  outside="$(gh_scoped api --paginate /user/repos \
    --jq ".[] | select(.private and .owner.login != \"$ORGANIZATION\") | .full_name")"
  [[ -z "$outside" ]]
}

signed_in_through_app() { [[ "$(gh_scoped auth token)" == ghu_* ]]; }

workspace_uses_sign_in() {
  [[ -s "$GIT_CREDENTIALS_FILE" && "$(stat -c %a "$GIT_CREDENTIALS_FILE")" == 600 ]] &&
    git -C "$REPOSITORY_DIR" config --get-all credential.https://github.com.helper |
    grep -qxF "store --file=$GIT_CREDENTIALS_FILE"
}

workspace_identity_set() {
  git -C "$REPOSITORY_DIR" config --show-origin user.email | grep -qF "$WORKSPACE_GITCONFIG"
}

# A failing connection to a site that is not on the allowlist.
site_blocked() { ! curl -sS -o /dev/null --max-time 10 https://example.com; }
no_global_github_helper() { ! git config --global --get-all credential.https://github.com.helper; }

# Prints "ok", "drift" or "unreadable" (merge settings are only visible with administration access).
merge_settings_state() {
  gh_scoped api "repos/$ORGANIZATION/$1" --jq '
    if .allow_squash_merge == null then "unreadable"
    elif .allow_squash_merge and (.allow_merge_commit | not) and (.allow_rebase_merge | not)
      and .squash_merge_commit_title == "PR_TITLE" and .squash_merge_commit_message == "PR_BODY"
      and .delete_branch_on_merge then "ok"
    else "drift" end'
}

drift() {
  warn "$1"
  failures=$((failures + 1))
}

# Compares the handbook's data/repositories.yaml with GitHub, in both directions.
check_repositories_match_handbook() {
  local -A visibility=() description=() topics=() documented=()
  local name status vis kind context language desc tops expected problems kinds topic
  local separator=$'\x1f'
  while IFS="$separator" read -r name vis desc tops; do
    visibility[$name]="$vis"
    description[$name]="$desc"
    topics[$name]="$tops"
  done < <(gh_scoped api --paginate "orgs/$ORGANIZATION/repos?per_page=100" \
    --jq '.[] | select(.archived | not) | [.name, .visibility, (.description // ""), (.topics | sort | join(","))] | join("\u001f")')

  while IFS="$separator" read -r name status vis kind context language desc; do
    documented[$name]=1
    if [[ "$status" == planned ]]; then
      [[ -z "${visibility[$name]+set}" ]] || drift "$name exists on GitHub but is planned in the handbook"
      continue
    fi
    if [[ -z "${visibility[$name]+set}" ]]; then
      drift "$name is active in the handbook but does not exist on GitHub"
      continue
    fi
    problems=()
    [[ "${visibility[$name]}" == "$vis" ]] || problems+=("visibility is ${visibility[$name]}, the handbook says $vis")
    [[ "${description[$name]}" == "$desc" ]] || problems+=("description differs from the handbook")
    expected="$(printf '%s\n' "$kind" ${context:+"context-$context"} ${language:+"language-$language"} | sort | paste -sd, -)"
    [[ "${topics[$name]}" == "$expected" ]] || problems+=("topics are '${topics[$name]}', the handbook implies '$expected'")
    if ((${#problems[@]} > 0)); then
      drift "$name: $(printf '%s; ' "${problems[@]}" | sed 's/; $//')"
    else
      ok "$name matches its entry in the handbook"
    fi
  done < <(handbook_data repositories)

  kinds=" $(handbook_data kinds | tr '\n' ' ')"
  for name in "${!topics[@]}"; do
    [[ -z "${documented[$name]+set}" ]] || continue
    for topic in ${topics[$name]//,/ }; do
      if [[ "$kinds" == *" $topic "* ]]; then
        drift "$name follows the conventions on GitHub but is missing from the handbook"
        break
      fi
    done
  done
}

# Every workspace repository uses the organization's git hooks, and no checked-out main is behind
# GitHub as last fetched by the workspace update.
check_workspace_repositories() {
  local directory name branch without_hooks=() behind=()
  for directory in "$WORKSPACE_DIR"/* "$WORKSPACE_DIR"/.[!.]*; do
    [[ -d "$directory/.git" ]] || continue
    name="$(basename "$directory")"
    if [[ "$(git -C "$directory" config core.hooksPath || true)" != "$REPOSITORY_DIR/hooks" ]]; then
      without_hooks+=("$name")
    fi
    branch="$(git -C "$directory" symbolic-ref --short --quiet HEAD || true)"
    if [[ "$branch" == main ]] && git -C "$directory" rev-parse --verify --quiet origin/main >/dev/null &&
      (($(git -C "$directory" rev-list --count main..origin/main) > 0)); then
      behind+=("$name")
    fi
  done
  if ((${#without_hooks[@]} > 0)); then
    drift "without the organization's git hooks: ${without_hooks[*]}. Run scripts/configure-git-hooks.sh."
  else
    ok "every workspace repository uses the organization's git hooks"
  fi
  if ((${#behind[@]} > 0)); then
    drift "main is behind GitHub in: ${behind[*]}. Run 'mise run update'; .workspace-update.md says why it was not updated."
  else
    ok "no checked-out main is behind GitHub"
  fi
}

playbook_installed() { command -v playbook || test -x "$HOME/.local/bin/playbook"; }

playbook_skills_installed() { compgen -G "${PLAYBOOK_SKILLS_DIR:-$HOME/.agents/skills}/bytelibrary-*/SKILL.md"; }

# Compares the project's Context options with the handbook's contexts (plus "organization").
check_contexts_match_project() {
  local expected actual missing extra
  expected="$( (handbook_data contexts; echo organization) | sort)"
  actual="$(gh_scoped api graphql -F number="$PROJECT_NUMBER" -f organization="$ORGANIZATION" -f query='
    query($organization: String!, $number: Int!) {
      organization(login: $organization) { projectV2(number: $number) { field(name: "Context") {
        ... on ProjectV2SingleSelectField { options { name } } } } }
    }' --jq '.data.organization.projectV2.field.options[].name' | sort)"
  missing="$(comm -23 <(echo "$expected") <(echo "$actual") | paste -sd, -)"
  extra="$(comm -13 <(echo "$expected") <(echo "$actual") | paste -sd, -)"
  if [[ -z "$missing$extra" ]]; then
    ok "project Context options match the handbook's contexts"
  else
    drift "project Context options differ from the handbook: missing [${missing}], not in the handbook [${extra}]"
  fi
}

check_repository_settings() {
  local name state
  while read -r name; do
    state="$(merge_settings_state "$name")"
    case "$state" in
      ok) ok "$name: repository settings" ;;
      unreadable) info "$name: repository settings not visible without administration access" ;;
      *) warn "$name: repository settings differ from the handbook"; failures=$((failures + 1)) ;;
    esac
  done < <(convention_repositories)
}

info "Tools"
check "git is installed" command -v git
check "gh is installed" command -v gh
check "mise is installed" command -v mise
check "Docker daemon is reachable" docker info
check "Docker Compose is available" docker compose version
check "the site allowlist is active" systemctl is-active --quiet bytelibrary-firewall.service bytelibrary-dns.service
check "an allowed site is reachable (github.com)" curl -fsS -o /dev/null --max-time 15 https://github.com
check "a site not on the allowlist is blocked (example.com)" site_blocked
host_mounts="$(findmnt --types fuse.sshfs --noheadings --output TARGET || true)"
if [[ -z "$host_mounts" ]]; then
  ok "no folder of your computer is mounted in the machine"
else
  warn "folders of your computer are mounted in the machine: $(tr '\n' ' ' <<<"$host_mounts")(multipass umount bytelibrary)"
  failures=$((failures + 1))
fi
recently_blocked="$("$REPOSITORY_DIR/scripts/firewall.sh" blocked | wc -l)"
if ((recently_blocked > 0)); then
  info "$recently_blocked site(s) were blocked in the last day: scripts/firewall.sh blocked"
fi

info "GitHub access"
if non_interactive; then
  info "Skipped without questions: the checks of a person's sign-in"
else
  check "gh is logged in, in its ByteLibrary-only configuration" gh_logged_in
  check "signed in through the ByteLibrary Developer Access App" signed_in_through_app
  check "the sign-in reaches no private repositories outside $ORGANIZATION" token_limited_to_organization
fi
check "workspace repositories authenticate with the sign-in, from a private file" workspace_uses_sign_in
check "workspace commit identity is set" workspace_identity_set
check "GitHub credentials are not configured outside the workspace" no_global_github_helper

info "Repository settings"
check_repository_settings

info "Handbook data matches GitHub"
if [[ -d "$HANDBOOK_DATA_DIR" ]]; then
  check_repositories_match_handbook
  check_contexts_match_project
else
  drift "the handbook is not cloned, so its data cannot be compared with GitHub"
fi

info "Workspace"
check "workspace AGENTS.md exists" test -f "$WORKSPACE_DIR/AGENTS.md"
check "workspace mise.toml exists" test -f "$WORKSPACE_DIR/mise.toml"
check "handbook is cloned" test -d "$WORKSPACE_DIR/handbook/.git"
check_workspace_repositories
check "the playbook command is installed" playbook_installed
check "the playbook's skills are in ${PLAYBOOK_SKILLS_DIR:-$HOME/.agents/skills}" playbook_skills_installed

info "Workspace updates"
if [[ -s "$UPDATE_REPORT_FILE" ]]; then
  sed 's/^/    /' "$UPDATE_REPORT_FILE"
else
  info "No update has run yet. Run 'mise run update'."
fi

info "Workspace updates"
if [[ -s "$UPDATE_REPORT_FILE" ]]; then
  sed 's/^/    /' "$UPDATE_REPORT_FILE"
else
  info "No update has run yet. Run 'mise run update'."
fi

if ((failures > 0)); then
  fail "$failures check(s) failed. See README.md, Troubleshooting."
fi
ok "Workspace is ready"
