#!/usr/bin/env bash
# Shared settings and helpers for the setup scripts. Sourced, not executed.
# The settings are used by the scripts that source this file, which shellcheck cannot see from here.
# shellcheck disable=SC2034
set -euo pipefail

ORGANIZATION="ByteLibrary"
WORKSPACE_DIR="${BYTELIBRARY_WORKSPACE_DIR:-$HOME/ByteLibrary}"
GH_CONFIG_DIR_SCOPED="${BYTELIBRARY_GH_CONFIG_DIR:-$HOME/.config/gh-bytelibrary}"
WORKSPACE_GITCONFIG="$HOME/.gitconfig-bytelibrary"
# The workspace update (scripts/update.sh): its report, which agents read too, and its lock.
UPDATE_REPORT_FILE="$WORKSPACE_DIR/.workspace-update.md"
UPDATE_LOCK_FILE="${BYTELIBRARY_UPDATE_LOCK_FILE:-$HOME/.cache/bytelibrary/update.lock}"
GIT_CREDENTIALS_FILE="${BYTELIBRARY_GIT_CREDENTIALS_FILE:-$HOME/.config/bytelibrary/git-credentials}"
# The ByteLibrary Developer Access GitHub App that developers sign in through (ADR-0026). Its client ID
# is public.
APP_CLIENT_ID="Iv23liYsI5hIzrbCg40q"
HANDBOOK_DATA_DIR="${BYTELIBRARY_HANDBOOK_DATA_DIR:-$WORKSPACE_DIR/handbook/data}"
PROJECT_NUMBER=1
REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# mise itself, pinned like every tool it installs (ADR-0028).
MISE_VERSION="v2026.10.3"

# mise and the tools it installs, also in shells where mise is not activated yet (such as setup's first
# run). The shims pick the version pinned by the nearest mise.toml.
PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:$PATH"

info() { printf '\033[34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m ok\033[0m %s\n' "$*"; }
warn() { printf '\033[33m !!\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[31mERR\033[0m %s\n' "$*" >&2; exit 1; }

confirm() {
  local reply
  # Without questions, every question is answered no.
  if non_interactive; then return 1; fi
  read -r -p "$1 [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

# Setup without questions, for CI: a token to use instead of the sign-in, and the commit identity.
# BYTELIBRARY_GITHUB_TOKEN, BYTELIBRARY_COMMIT_NAME, BYTELIBRARY_COMMIT_EMAIL
non_interactive() { [[ -n "${BYTELIBRARY_GITHUB_TOKEN:-}" ]]; }

# gh, always with the ByteLibrary-only login, or with the given token without questions.
gh_scoped() {
  if non_interactive; then
    GH_TOKEN="$BYTELIBRARY_GITHUB_TOKEN" gh "$@"
  else
    GH_CONFIG_DIR="$GH_CONFIG_DIR_SCOPED" gh "$@"
  fi
}

# Stores a token for git, in the workspace credentials file only. Reads the token from standard input.
store_git_credentials() {
  local token
  token="$(cat)"
  mkdir -p "$(dirname "$GIT_CREDENTIALS_FILE")"
  (
    umask 077
    printf 'protocol=https\nhost=github.com\nusername=x-access-token\npassword=%s\n\n' "$token" |
      git credential-store --file "$GIT_CREDENTIALS_FILE" store
  )
}

# Facts from the handbook's data tables (see handbook_data.py). Uses the handbook's own environment, which
# has the pinned YAML library, once it exists; the system Python until then.
handbook_data() {
  # The system's Python, which has PyYAML (install-system-packages.sh); mise's Python may not.
  local python=/usr/bin/python3
  [[ -x "$WORKSPACE_DIR/handbook/.venv/bin/python" ]] && python="$WORKSPACE_DIR/handbook/.venv/bin/python"
  [[ -d "$HANDBOOK_DATA_DIR" ]] || fail "The handbook's data is missing: $HANDBOOK_DATA_DIR"
  "$python" "$REPOSITORY_DIR/scripts/handbook_data.py" "$HANDBOOK_DATA_DIR" "$1"
}

# Prints the names of the non-archived repositories that follow the conventions: those with a kind topic
# from the handbook's repository kinds. Scripts that work on "every repository" ignore all others.
convention_repositories() {
  local kinds
  kinds="$(handbook_data kinds | sed 's/.*/"&"/' | paste -sd, -)"
  gh_scoped api --paginate "orgs/$ORGANIZATION/repos?per_page=100" \
    --jq ".[] | select((.archived | not) and any(.topics[]; IN($kinds))) | .name"
}
