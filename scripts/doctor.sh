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

workspace_uses_token() {
  git -C "$REPOSITORY_DIR" config --get-all credential.https://github.com.helper |
    grep -qF "GH_CONFIG_DIR=$GH_CONFIG_DIR_SCOPED"
}

workspace_identity_set() {
  git -C "$REPOSITORY_DIR" config --show-origin user.email | grep -qF "$WORKSPACE_GITCONFIG"
}

no_global_github_helper() { ! git config --global --get-all credential.https://github.com.helper; }

info "Tools"
check "git is installed" command -v git
check "gh is installed" command -v gh
check "mise is installed" command -v mise
check "Docker daemon is reachable" docker info
check "Docker Compose is available" docker compose version

info "GitHub access"
check "gh is logged in with the workspace token" gh_logged_in
check "token reaches no private repositories outside $ORGANIZATION" token_limited_to_organization
check "workspace repositories authenticate with the workspace token" workspace_uses_token
check "workspace commit identity is set" workspace_identity_set
check "GitHub credentials are not configured outside the workspace" no_global_github_helper

info "Workspace"
check "workspace AGENTS.md exists" test -f "$WORKSPACE_DIR/AGENTS.md"
check "workspace mise.toml exists" test -f "$WORKSPACE_DIR/mise.toml"
check "organization-handbook is cloned" test -d "$WORKSPACE_DIR/organization-handbook/.git"

if ((failures > 0)); then
  fail "$failures check(s) failed. See README.md, Troubleshooting."
fi
ok "Workspace is ready"
