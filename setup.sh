#!/usr/bin/env bash
# Sets up the workspace in the development machine. Safe to run again at any time.
source "$(dirname "$0")/scripts/lib.sh"

# The workspace's mise.toml decides the tools' versions, so setup runs from the workspace.
mkdir -p "$WORKSPACE_DIR"
cd "$WORKSPACE_DIR" || exit

"$REPOSITORY_DIR/scripts/install-system-packages.sh"
"$REPOSITORY_DIR/scripts/configure-firewall.sh"
"$REPOSITORY_DIR/scripts/authorize-ssh-key.sh"
"$REPOSITORY_DIR/scripts/write-workspace-files.sh"
"$REPOSITORY_DIR/scripts/install-tools.sh"
"$REPOSITORY_DIR/scripts/configure-github-access.sh"
"$REPOSITORY_DIR/scripts/configure-git-hooks.sh"
"$REPOSITORY_DIR/scripts/clone-repositories.sh"
"$REPOSITORY_DIR/scripts/install-tools.sh" repositories
"$REPOSITORY_DIR/scripts/write-workspace-files.sh"
"$REPOSITORY_DIR/scripts/install-playbook.sh"
"$REPOSITORY_DIR/scripts/configure-updates.sh"

# A docker group membership added by this run only applies to new sessions; check with it already.
# `id -nG` without a user lists this session's groups; with a user, it would read the updated group file.
if id -nG | tr ' ' '\n' | grep -qx docker || ! getent group docker | grep -qw "$USER"; then
  "$REPOSITORY_DIR/scripts/doctor.py"
else
  sg docker -c "$REPOSITORY_DIR/scripts/doctor.py"
fi
