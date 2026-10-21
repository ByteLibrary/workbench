#!/usr/bin/env bash
# Keeps the workspace up to date in the background (ADR-0023): a systemd user timer runs
# scripts/update.py every 10 minutes, and, if the developer agrees, the report shows when a terminal
# opens.
source "$(dirname "$0")/lib.sh"

units="$HOME/.config/systemd/user"
if ! systemctl --user show-environment >/dev/null 2>&1; then
  warn "systemd user services are not available here; run 'mise run update' to update the workspace"
else
  mkdir -p "$units"
  cat >"$units/bytelibrary-update.service" <<UNIT
[Unit]
Description=Update the ByteLibrary workspace

[Service]
Type=oneshot
Environment=BYTELIBRARY_WORKSPACE_DIR=$WORKSPACE_DIR
# The Python workbench pins; setup writes this again when the pin changes.
ExecStart=$(configured_python "$REPOSITORY_DIR") $REPOSITORY_DIR/scripts/update.py
UNIT
  cat >"$units/bytelibrary-update.timer" <<UNIT
[Unit]
Description=Update the ByteLibrary workspace every 10 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min

[Install]
WantedBy=timers.target
UNIT
  systemctl --user daemon-reload
  systemctl --user enable --now bytelibrary-update.timer >/dev/null 2>&1
  ok "The workspace updates itself every 10 minutes (systemd user timer bytelibrary-update.timer)"
fi

# The report when a terminal opens: one line in ~/.bashrc, only with the developer's agreement.
line="[[ -s \"$UPDATE_REPORT_FILE\" ]] && cat \"$UPDATE_REPORT_FILE\""
if grep -qxF "$line" "$HOME/.bashrc" 2>/dev/null; then
  ok "The update report shows when a terminal opens"
elif confirm "Show the workspace update report when a terminal opens (adds one line to ~/.bashrc)?"; then
  printf '\n# ByteLibrary workspace update report (workbench/scripts/configure-updates.sh)\n%s\n' "$line" >>"$HOME/.bashrc"
  ok "The update report shows when a terminal opens"
fi
