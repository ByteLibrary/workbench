#!/usr/bin/env bash
# Shared settings and helpers for the setup scripts. Sourced, not executed.
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
