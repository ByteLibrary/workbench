#!/usr/bin/env bash
# Shared settings and helpers for the setup scripts. Sourced, not executed.
# The settings are used by the scripts that source this file, which shellcheck cannot see from here.
# shellcheck disable=SC2034
set -euo pipefail

ORGANIZATION="ByteLibrary"
WORKSPACE_DIR="${BYTELIBRARY_WORKSPACE_DIR:-$HOME/ByteLibrary}"
GH_CONFIG_DIR_SCOPED="${BYTELIBRARY_GH_CONFIG_DIR:-$HOME/.config/gh-bytelibrary}"
WORKSPACE_GITCONFIG="$HOME/.gitconfig-bytelibrary"
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

# Kind topics from the handbook's repository conventions. Only repositories with one of them follow the
# conventions; scripts that work on "every repository" ignore all others.
KIND_TOPICS='"service","worker","library","template","application","documentation","infrastructure","tooling","planning"'

# Prints the names of the non-archived repositories that follow the conventions.
convention_repositories() {
  gh_scoped api --paginate "orgs/$ORGANIZATION/repos?per_page=100" \
    --jq ".[] | select((.archived | not) and any(.topics[]; IN($KIND_TOPICS))) | .name"
}
