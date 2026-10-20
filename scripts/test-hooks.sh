#!/usr/bin/env bash
# Tests the organization's git hooks in a throwaway workspace, against a local bare repository, with
# the rules script from reusable-ci-workflows (RULES_REPOSITORY, default: the workspace clone).
set -euo pipefail

repository_dir="$(cd "$(dirname "$0")/.." && pwd)"
rules_repository="$(cd "${RULES_REPOSITORY:-$repository_dir/../reusable-ci-workflows}" && pwd)"
[[ -x "$rules_repository/scripts/standards.py" ]] || { echo "rules script not found in $rules_repository" >&2; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
export BYTELIBRARY_WORKSPACE_DIR="$work/workspace" HOME="$work/home"
mkdir -p "$BYTELIBRARY_WORKSPACE_DIR" "$HOME"
ln -s "$rules_repository" "$BYTELIBRARY_WORKSPACE_DIR/reusable-ci-workflows"
git init -q --bare "$work/remote.git"
git init -q -b main "$BYTELIBRARY_WORKSPACE_DIR/example"
cd "$BYTELIBRARY_WORKSPACE_DIR/example"
git config user.name "Test" && git config user.email "test@example.com"
git remote add origin "$work/remote.git"
# The hooks are not applied yet: create main on the remote the way GitHub does when a repository is made.
git commit -q --allow-empty -m "chore: start" && git push -q origin main

failures=0
expect() {
  local outcome="$1" description="$2"
  shift 2
  if "$@" >/dev/null 2>&1; then actual=pass; else actual=fail; fi
  if [[ "$actual" == "$outcome" ]]; then
    echo "ok   $description"
  else
    echo "FAIL $description: expected $outcome, got $actual"
    failures=$((failures + 1))
  fi
}

"$repository_dir/scripts/configure-git-hooks.sh" >/dev/null
expect pass "setup applies the hooks through the workspace git configuration" \
  test "$(git config --file "$HOME/.gitconfig-bytelibrary" core.hooksPath)" = "$repository_dir/hooks"
git config core.hooksPath "$repository_dir/hooks"

git switch -q -c feat/1-example
expect pass "commit: conventional message" git commit -q --allow-empty -m "feat: add an example"
expect fail "commit: not conventional" git commit -q --allow-empty -m "Add an example"
expect fail "commit: co-author trailer" git commit -q --allow-empty -m "feat: add an example" -m "Co-authored-by: someone <someone@example.com>"
git switch -q main && git commit -q --no-verify --allow-empty -m "docs: change main locally" && git switch -q feat/1-example
expect pass "commit: merge with git's own message" git merge -q --no-edit --no-ff main
expect pass "push: conventional branch" git push -q origin feat/1-example
expect fail "push: branch name without an issue" git push -q origin HEAD:refs/heads/example-branch
expect fail "push: to main" git push -q origin HEAD:refs/heads/main
expect fail "push: deleting main" git push -q origin --delete main
expect pass "push: deleting a branch" git push -q origin --delete feat/1-example
expect pass "push: a tag" git push -q origin HEAD:refs/tags/v0.0.1

rm "$BYTELIBRARY_WORKSPACE_DIR/reusable-ci-workflows"
expect fail "commit: refused when the rules are missing" git commit -q --allow-empty -m "feat: add an example"

if ((failures > 0)); then
  echo "$failures test(s) failed"
  exit 1
fi
echo "all tests passed"
