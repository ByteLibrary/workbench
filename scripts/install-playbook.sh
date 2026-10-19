#!/usr/bin/env bash
# Installs the playbook from its workspace clone with its own installer (ADR-0029 of the handbook): the
# `playbook` command, and its skills in ~/.agents/skills/. Safe to run again.
source "$(dirname "$0")/lib.sh"

playbook="$WORKSPACE_DIR/playbook"
[[ -x "$playbook/install.sh" ]] || fail "The playbook is not cloned ($playbook). Run setup.sh."

if command -v mise >/dev/null; then
  # The playbook pins its own Python and uv; install them first, then run its installer with them.
  (cd "$playbook" && mise trust --quiet && mise install --quiet && mise exec -- ./install.sh)
elif command -v uv >/dev/null; then
  "$playbook/install.sh"
else
  warn "Skipped installing the playbook: it needs mise (or uv). Run this again once mise is installed."
  exit 0
fi
ok "The playbook's commands and skills are installed"
