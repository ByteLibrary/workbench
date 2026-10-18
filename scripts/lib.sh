#!/usr/bin/env bash
# Shared settings and helpers for the setup scripts. Sourced, not executed.
# The settings are used by the scripts that source this file, which shellcheck cannot see from here.
# shellcheck disable=SC2034
set -euo pipefail

ORGANIZATION="ByteLibrary"
WORKSPACE_DIR="${BYTELIBRARY_WORKSPACE_DIR:-$HOME/ByteLibrary}"
GH_CONFIG_DIR_SCOPED="${BYTELIBRARY_GH_CONFIG_DIR:-$HOME/.config/gh-bytelibrary}"
WORKSPACE_GITCONFIG="$HOME/.gitconfig-bytelibrary"
GIT_CREDENTIALS_FILE="${BYTELIBRARY_GIT_CREDENTIALS_FILE:-$HOME/.config/bytelibrary/git-credentials}"
# The ByteLibrary Developer Access GitHub App that developers sign in through (ADR-0026). Its client ID
# is public.
APP_CLIENT_ID="Iv23liYsI5hIzrbCg40q"
HANDBOOK_DATA_DIR="${BYTELIBRARY_HANDBOOK_DATA_DIR:-$WORKSPACE_DIR/handbook/data}"
PROJECT_NUMBER=1
REPOSITORY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

info() { printf '\033[34m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m ok\033[0m %s\n' "$*"; }
warn() { printf '\033[33m !!\033[0m %s\n' "$*" >&2; }
fail() { printf '\033[31mERR\033[0m %s\n' "$*" >&2; exit 1; }

confirm() {
  local reply
  read -r -p "$1 [y/N] " reply
  [[ "$reply" =~ ^[Yy]$ ]]
}

# gh, always with the ByteLibrary-only login.
gh_scoped() { GH_CONFIG_DIR="$GH_CONFIG_DIR_SCOPED" gh "$@"; }

# Facts from the handbook's data tables (see handbook_data.py). Uses the handbook's own environment, which
# has the pinned YAML library, once it exists; the system Python until then.
handbook_data() {
  local python=python3
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
