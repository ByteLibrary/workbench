#!/usr/bin/env bash
# Makes gh and git use the ByteLibrary-only token, and only inside the workspace.
# See docs/github-access-token.md.
source "$(dirname "$0")/lib.sh"

info "Configuring GitHub access for $WORKSPACE_DIR"

# 1. gh login, kept in its own configuration directory.
if gh_scoped auth status --hostname github.com >/dev/null 2>&1; then
  ok "gh is logged in with the workspace token ($GH_CONFIG_DIR_SCOPED)"
elif [[ -f "$HOME/.config/gh/hosts.yml" ]] \
  && confirm "Move your existing gh login (~/.config/gh) to the ByteLibrary-only configuration?"; then
  mkdir -p "$(dirname "$GH_CONFIG_DIR_SCOPED")"
  mv "$HOME/.config/gh" "$GH_CONFIG_DIR_SCOPED"
  ok "Moved the gh login to $GH_CONFIG_DIR_SCOPED"
else
  info "Log in with the fine-grained token (docs/github-access-token.md, step 2)"
  gh_scoped auth login --hostname github.com --git-protocol https
fi

# 2. Commit identity, used only for repositories under the workspace.
if [[ ! -f "$WORKSPACE_GITCONFIG" ]]; then
  name="$(git config --global user.name || true)"
  email="$(git config --global user.email || true)"
  read -r -p "Commit name for $ORGANIZATION [$name]: " input && name="${input:-$name}"
  read -r -p "Commit email for $ORGANIZATION [$email]: " input && email="${input:-$email}"
  [[ -n "$name" && -n "$email" ]] || fail "A commit name and email are required"
  git config --file "$WORKSPACE_GITCONFIG" user.name "$name"
  git config --file "$WORKSPACE_GITCONFIG" user.email "$email"
fi

# 3. Credentials for github.com: only the workspace token. The empty helper clears any other helper.
git config --file "$WORKSPACE_GITCONFIG" --unset-all credential.https://github.com.helper || true
git config --file "$WORKSPACE_GITCONFIG" --add credential.https://github.com.helper ""
git config --file "$WORKSPACE_GITCONFIG" --add credential.https://github.com.helper \
  "!GH_CONFIG_DIR=$GH_CONFIG_DIR_SCOPED gh auth git-credential"

# 4. Load that file only for repositories under the workspace.
git config --global "includeIf.gitdir:$WORKSPACE_DIR/.path" "$WORKSPACE_GITCONFIG"
ok "git uses $WORKSPACE_GITCONFIG for repositories under $WORKSPACE_DIR/"

# 5. "gh auth setup-git" adds machine-wide helpers that would use the token everywhere.
if git config --global --get-all credential.https://github.com.helper >/dev/null 2>&1; then
  warn "Your global git configuration sends GitHub credentials through gh outside the workspace too."
  if confirm "Remove the global GitHub credential helpers (a backup of ~/.gitconfig is kept)?"; then
    cp "$HOME/.gitconfig" "$HOME/.gitconfig.backup-$(date +%Y%m%d%H%M%S)"
    git config --global --unset-all credential.https://github.com.helper
    git config --global --unset-all credential.https://gist.github.com.helper || true
    ok "Removed the global GitHub credential helpers"
  fi
fi
