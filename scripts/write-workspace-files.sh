#!/usr/bin/env bash
# Writes the workspace-level files (mise.toml, agent instructions) into the workspace root.
source "$(dirname "$0")/lib.sh"

info "Writing workspace files into $WORKSPACE_DIR"

cp "$REPOSITORY_DIR/workspace/mise.toml" "$WORKSPACE_DIR/mise.toml"
cp "$REPOSITORY_DIR/workspace/AGENTS.md" "$WORKSPACE_DIR/AGENTS.md"
ok "mise.toml and AGENTS.md"

# A VS Code workspace file that opens every repository in one window: the handbook first, then the
# others in alphabetical order, hidden ones last (ADR-0023).
repositories=()
for directory in "$WORKSPACE_DIR"/handbook "$WORKSPACE_DIR"/* "$WORKSPACE_DIR"/.[!.]*; do
  name="$(basename "$directory")"
  [[ -d "$directory/.git" ]] || continue
  [[ " ${repositories[*]} " == *" $name "* ]] || repositories+=("$name")
done
{
  printf '{\n  "folders": [\n'
  for index in "${!repositories[@]}"; do
    separator=","
    ((index == ${#repositories[@]} - 1)) && separator=""
    printf '    { "path": "%s" }%s\n' "${repositories[$index]}" "$separator"
  done
  printf '  ]\n}\n'
} >"$WORKSPACE_DIR/ByteLibrary.code-workspace"
ok "ByteLibrary.code-workspace (${#repositories[@]} repositories)"

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
