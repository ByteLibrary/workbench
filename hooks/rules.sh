# shellcheck shell=bash
# Runs the organization's rules script from the workspace clone of reusable-ci-workflows. Sourced by the
# hooks, after lib.sh.
rules() {
  local script="$WORKSPACE_DIR/reusable-ci-workflows/scripts/standards.py"
  [[ -x "$script" ]] || fail "The organization's rules are missing ($script). Run setup.sh, which clones reusable-ci-workflows."
  "$script" "$@" || fail "Fix the problems above, then try again."
}
