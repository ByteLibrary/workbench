#!/usr/bin/env bash
# Sets up a ByteLibrary workspace. Safe to run again at any time.
source "$(dirname "$0")/scripts/lib.sh"

command -v git >/dev/null || fail "git is required (see README.md, Prerequisites)"
command -v gh >/dev/null || fail "gh is required (see README.md, Prerequisites)"
command -v mise >/dev/null || warn "mise is not installed yet (see README.md, Prerequisites)"

"$REPOSITORY_DIR/scripts/configure-github-access.sh"
"$REPOSITORY_DIR/scripts/configure-git-hooks.sh"
"$REPOSITORY_DIR/scripts/clone-repositories.sh"
"$REPOSITORY_DIR/scripts/write-workspace-files.sh"
"$REPOSITORY_DIR/scripts/doctor.sh"
