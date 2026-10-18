#!/usr/bin/env bash
# Makes every repository under the workspace use the organization's git hooks (hooks/, ADR-0024).
source "$(dirname "$0")/lib.sh"

git config --file "$WORKSPACE_GITCONFIG" core.hooksPath "$REPOSITORY_DIR/hooks"
ok "Repositories under $WORKSPACE_DIR/ use the organization's git hooks"
