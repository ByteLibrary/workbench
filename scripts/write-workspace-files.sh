#!/usr/bin/env bash
# Writes the workspace-level files (mise.toml, agent instructions) into the workspace root.
source "$(dirname "$0")/lib.sh"

info "Writing workspace files into $WORKSPACE_DIR"

cp "$REPOSITORY_DIR/workspace/mise.toml" "$WORKSPACE_DIR/mise.toml"
cp "$REPOSITORY_DIR/workspace/AGENTS.md" "$WORKSPACE_DIR/AGENTS.md"
ok "mise.toml and AGENTS.md"

# Agent tools that need their own instruction file get the same compatibility pointers the
# handbook uses (ADR-0017): any top-level file whose only content is "@AGENTS.md".
handbook="$WORKSPACE_DIR/handbook"
if [[ -d "$handbook" ]]; then
  for file in "$handbook"/*.md; do
    if [[ "$(basename "$file")" != "AGENTS.md" && "$(cat "$file")" == "@AGENTS.md" ]]; then
      cp "$file" "$WORKSPACE_DIR/"
      ok "$(basename "$file") (pointer to AGENTS.md)"
    fi
  done
else
  warn "handbook is not cloned; skipped agent instruction pointers"
fi

if command -v mise >/dev/null; then
  mise trust --quiet "$WORKSPACE_DIR/mise.toml"
  ok "mise trusts the workspace configuration"
fi
