#!/usr/bin/env bash
# Lets the developer's editor connect over SSH: authorizes the public key the README copies into the
# machine. Safe to run again.
source "$(dirname "$0")/lib.sh"

authorized="$HOME/.ssh/authorized_keys"
if [[ -s "$EDITOR_SSH_KEY_FILE" ]]; then
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  touch "$authorized" && chmod 600 "$authorized"
  # PowerShell ends piped lines with a carriage return.
  key="$(tr -d '\r' <"$EDITOR_SSH_KEY_FILE")"
  if ! grep -qxF "$key" "$authorized"; then
    echo "$key" >>"$authorized"
  fi
  rm "$EDITOR_SSH_KEY_FILE"
  ok "Your editor's SSH key is authorized"
else
  info "No new SSH key to authorize (README, Setup, step 2)"
fi
