#!/usr/bin/env bash
# Clones every repository that follows the conventions and is not in the workspace yet.
source "$(dirname "$0")/lib.sh"

info "Cloning $ORGANIZATION repositories into $WORKSPACE_DIR"
mkdir -p "$WORKSPACE_DIR"

# The handbook comes first: the other repositories are listed from its data.
if [[ ! -d "$WORKSPACE_DIR/handbook/.git" ]]; then
  gh_scoped repo clone "$ORGANIZATION/handbook" "$WORKSPACE_DIR/handbook" -- --quiet
  ok "handbook (cloned)"
fi

convention_repositories |
  while read -r name; do
    if [[ -d "$WORKSPACE_DIR/$name/.git" ]]; then
      ok "$name (already cloned)"
    else
      gh_scoped repo clone "$ORGANIZATION/$name" "$WORKSPACE_DIR/$name" -- --quiet
      ok "$name (cloned)"
    fi
  done
