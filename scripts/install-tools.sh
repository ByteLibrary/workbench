#!/usr/bin/env bash
# Installs mise and, through it, the tools at the versions pinned in git (ADR-0028 of the handbook): the
# workspace's own tools, then every repository's. Safe to run again.
source "$(dirname "$0")/lib.sh"

if ! command -v mise >/dev/null; then
  info "Installing mise $MISE_VERSION"
  curl -fsSL https://mise.run | MISE_VERSION="$MISE_VERSION" sh >/dev/null
fi
ok "mise $(mise --version | cut -d' ' -f1)"

# mise puts the pinned tools on the PATH of every new shell, once activated.
line='eval "$(mise activate bash)"'
if grep -qxF "$line" "$HOME/.bashrc" 2>/dev/null; then
  ok "mise is activated in new shells"
elif confirm "Activate mise in new shells (adds one line to ~/.bashrc)?"; then
  printf '\n# mise: tools at the versions pinned in each repository (workbench/scripts/install-tools.sh)\n%s\n' "$line" >>"$HOME/.bashrc"
  ok "mise is activated in new shells"
fi

# Every mise.toml in the workspace, the workspace's own first; "repositories" also covers new clones.
directories=("$WORKSPACE_DIR")
if [[ "${1:-}" == repositories ]]; then
  for directory in "$WORKSPACE_DIR"/* "$WORKSPACE_DIR"/.[!.]*; do
    if [[ -f "$directory/mise.toml" ]]; then
      directories+=("$directory")
    fi
  done
fi
for directory in "${directories[@]}"; do
  if [[ ! -f "$directory/mise.toml" ]]; then
    continue
  fi
  (cd "$directory" && mise trust --quiet && mise install --quiet)
  ok "Tools for $(basename "$directory")"
done
