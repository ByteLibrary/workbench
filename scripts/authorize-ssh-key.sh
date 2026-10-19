#!/usr/bin/env bash
# Lets the developer's editor connect over SSH: authorizes the public key the README copies into the
# machine. Safe to run again.
source "$(dirname "$0")/lib.sh"

authorized="$HOME/.ssh/authorized_keys"
if [[ -s "$EDITOR_SSH_KEY_FILE" ]]; then
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  touch "$authorized" && chmod 600 "$authorized"
  if ! grep -qxF "$(cat "$EDITOR_SSH_KEY_FILE")" "$authorized"; then
    cat "$EDITOR_SSH_KEY_FILE" >>"$authorized"
  fi
  rm "$EDITOR_SSH_KEY_FILE"
  ok "Your editor's SSH key is authorized"
else
  info "No new SSH key to authorize (README, Setup, step 2)"
fi
