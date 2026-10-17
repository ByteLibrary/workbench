#!/usr/bin/env bash
# Clones every repository that follows the conventions and is not in the workspace yet.
source "$(dirname "$0")/lib.sh"

info "Cloning $ORGANIZATION repositories into $WORKSPACE_DIR"
mkdir -p "$WORKSPACE_DIR"

convention_repositories |
  while read -r name; do
    if [[ -d "$WORKSPACE_DIR/$name/.git" ]]; then
      ok "$name (already cloned)"
    else
      gh_scoped repo clone "$ORGANIZATION/$name" "$WORKSPACE_DIR/$name" -- --quiet
      ok "$name (cloned)"
    fi
  done
