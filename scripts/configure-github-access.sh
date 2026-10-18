#!/usr/bin/env bash
# Signs in through the ByteLibrary Developer Access App and makes gh and git use that sign-in, and only
# inside the workspace. See docs/github-access.md.
source "$(dirname "$0")/lib.sh"

info "Configuring GitHub access for $WORKSPACE_DIR"

# 1. Sign-in (ADR-0026). gh keeps it in its own configuration directory; git in the workspace credentials.
app=true
current="$(gh_scoped auth token 2>/dev/null || true)"
if [[ "$current" == ghu_* && -s "$GIT_CREDENTIALS_FILE" ]]; then
  ok "Signed in through the ByteLibrary Developer Access App"
elif [[ -n "$current" && "$current" != ghu_* ]] &&
  ! confirm "The workspace uses a personal access token, which the App sign-in replaces. Sign in through the App now?"; then
  app=false
  warn "Kept the personal access token. Run scripts/sign-in.sh to switch later."
else
  "$REPOSITORY_DIR/scripts/sign-in.sh"
fi

# 2. Commit identity, used only for repositories under the workspace. GitHub's noreply address keeps the
# personal address out of commits.
if ! git config --file "$WORKSPACE_GITCONFIG" user.email >/dev/null 2>&1; then
  name="$(git config --global user.name || gh_scoped api user --jq '.name // .login')"
  email="$(gh_scoped api user --jq '"\(.id)+\(.login)@users.noreply.github.com"')"
  read -r -p "Commit name for $ORGANIZATION [$name]: " input && name="${input:-$name}"
  read -r -p "Commit email for $ORGANIZATION [$email]: " input && email="${input:-$email}"
  [[ -n "$name" && -n "$email" ]] || fail "A commit name and email are required"
  git config --file "$WORKSPACE_GITCONFIG" user.name "$name"
  git config --file "$WORKSPACE_GITCONFIG" user.email "$email"
fi

# 3. Credentials for github.com: only the workspace's. The empty helper clears any other helper.
git config --file "$WORKSPACE_GITCONFIG" --unset-all credential.https://github.com.helper || true
git config --file "$WORKSPACE_GITCONFIG" --add credential.https://github.com.helper ""
if [[ "$app" == true ]]; then
  git config --file "$WORKSPACE_GITCONFIG" --add credential.https://github.com.helper \
    "store --file=$GIT_CREDENTIALS_FILE"
else
  git config --file "$WORKSPACE_GITCONFIG" --add credential.https://github.com.helper \
    "!GH_CONFIG_DIR=$GH_CONFIG_DIR_SCOPED gh auth git-credential"
fi

# 4. Load that file only for repositories under the workspace.
git config --global "includeIf.gitdir:$WORKSPACE_DIR/.path" "$WORKSPACE_GITCONFIG"
ok "git uses $WORKSPACE_GITCONFIG for repositories under $WORKSPACE_DIR/"

# 5. "gh auth setup-git" adds machine-wide helpers that would send GitHub credentials outside the workspace.
if git config --global --get-all credential.https://github.com.helper >/dev/null 2>&1; then
  warn "Your global git configuration sends GitHub credentials through gh outside the workspace too."
  if confirm "Remove the global GitHub credential helpers (a backup of ~/.gitconfig is kept)?"; then
    cp "$HOME/.gitconfig" "$HOME/.gitconfig.backup-$(date +%Y%m%d%H%M%S)"
    git config --global --unset-all credential.https://github.com.helper
    git config --global --unset-all credential.https://gist.github.com.helper || true
    ok "Removed the global GitHub credential helpers"
  fi
fi
