#!/usr/bin/env python3
"""Keeps the workspace up to date (ADR-0023). Fetches every workspace repository, fast-forwards `main`
where it is checked out without local changes, and clones new organization repositories. Everything that
needs a decision is only reported, in the workspace's .workspace-update.md. Run every 10 minutes by a
systemd user timer (scripts/configure-updates.sh), and by `mise run update`.

Usage: mise run update   (in the workspace; or workbench/scripts/update.py)

Uses only the standard library, so the system's Python runs it from the timer.
"""

import datetime
import fcntl
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
HOME = Path.home()
WORKSPACE = Path(os.environ.get("BYTELIBRARY_WORKSPACE_DIR", HOME / "ByteLibrary"))
REPORT_FILE = WORKSPACE / ".workspace-update.md"
LOCK_FILE = Path(
    os.environ.get("BYTELIBRARY_UPDATE_LOCK_FILE", HOME / ".cache" / "bytelibrary" / "update.lock")
)
# A line clone-repositories.sh prints for each repository it cloned: "… <name> (cloned)".
CLONED = re.compile(r"^.* (\S+) \(cloned\)$", re.MULTILINE)


def git(directory: Path, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(directory), *arguments], capture_output=True, text=True)


def output(directory: Path, *arguments: str) -> str:
    return git(directory, *arguments).stdout.strip()


def count(directory: Path, revisions: str) -> int:
    return int(output(directory, "rev-list", "--count", revisions) or 0)


def busy(directory: Path) -> bool:
    """A git operation is in progress, so the repository must not be touched now."""
    git_dir = directory / output(directory, "rev-parse", "--git-dir")
    return (git_dir / "index.lock").exists() or any(
        (git_dir / name).exists()
        for name in ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD")
    )


class Update:
    def __init__(self) -> None:
        self.report: list[str] = []

    def note(self, line: str) -> None:
        self.report.append(line)

    def reinstall_playbook(self) -> None:
        """A changed or newly cloned playbook is installed again, so its commands and skills stay current."""
        if not shutil.which("mise") and not shutil.which("uv"):
            self.note(
                "playbook: changed, but not installed again: it needs mise; "
                "run workbench/scripts/install-playbook.sh once mise is installed"
            )
            return
        installer = str(REPOSITORY / "scripts" / "install-playbook.sh")
        if subprocess.run([installer], capture_output=True).returncode == 0:
            self.note("playbook: installed again")
        else:
            self.note("playbook: could not be installed again; run workbench/scripts/install-playbook.sh")

    def repository(self, directory: Path) -> None:
        name = directory.name
        if busy(directory):
            self.note(f"{name}: skipped, a git operation is in progress")
            return
        if git(directory, "fetch", "--quiet", "--prune", "origin").returncode != 0:
            self.note(f"{name}: could not fetch from GitHub; check the sign-in with mise run doctor")
            return
        if git(directory, "rev-parse", "--verify", "--quiet", "origin/main").returncode != 0:
            return
        branch = output(directory, "symbolic-ref", "--short", "--quiet", "HEAD")
        if branch == "main":
            self.main(directory, name)
        elif branch:
            self.branch(directory, name, branch)

    def main(self, directory: Path, name: str) -> None:
        behind, ahead = count(directory, "main..origin/main"), count(directory, "origin/main..main")
        if ahead:
            self.note(f"{name}: main has {ahead} commit(s) that are not on GitHub; move them to a branch")
        elif not behind:
            return
        elif output(directory, "status", "--porcelain", "--untracked-files=no"):
            self.note(f"{name}: {behind} new commit(s) on main, not applied: there are local changes")
        elif git(directory, "merge", "--ff-only", "--quiet", "origin/main").returncode == 0:
            self.note(f"{name}: updated, {behind} new commit(s)")
            if name == "workbench":
                self.note("workbench changed: run workbench/setup.sh to apply it")
            if name == "playbook":
                self.reinstall_playbook()
        else:
            self.note(f"{name}: {behind} new commit(s) on main, not applied: git refused to fast-forward")

    def branch(self, directory: Path, name: str, branch: str) -> None:
        tracked = output(directory, "config", f"branch.{branch}.remote")
        if tracked and git(directory, "rev-parse", "--verify", "--quiet", f"origin/{branch}").returncode != 0:
            self.note(f"{name}: {branch} was merged or deleted on GitHub; switch to main and delete it")
        behind = count(directory, "HEAD..origin/main")
        if behind:
            self.note(f"{name}: {branch} is {behind} commit(s) behind main")

    def new_repositories(self) -> None:
        """New repositories, and the workspace files that list them."""
        cloned = subprocess.run(
            [str(REPOSITORY / "scripts" / "clone-repositories.sh")], capture_output=True, text=True
        )
        if cloned.returncode != 0:
            self.note(
                "could not list the organization's repositories; check the sign-in with mise run doctor"
            )
            return
        new = CLONED.findall(cloned.stdout)
        if new:
            self.note(f"cloned new repositories: {', '.join(new)}")
            subprocess.run([str(REPOSITORY / "scripts" / "write-workspace-files.sh")], capture_output=True)
            if "playbook" in new:
                self.reinstall_playbook()

    def write_report(self) -> str:
        lines = [f"# Workspace update, {datetime.datetime.now():%Y-%m-%d %H:%M}"]
        lines += [f"- {line}" for line in self.report] or ["Everything is up to date."]
        text = "\n".join(lines) + "\n"
        REPORT_FILE.write_text(text, encoding="utf-8")
        return text


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w") as lock:
        # One run at a time: a run that finds another one in progress leaves it to finish.
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            arrow = "\033[34m==>\033[0m" if sys.stdout.isatty() else "==>"
            print(f"{arrow} Another update is running")
            return 0
        update = Update()
        # Visible folders first, then hidden ones such as .github, each in name order.
        for directory in sorted(WORKSPACE.iterdir(), key=lambda path: (path.name.startswith("."), path.name)):
            if (directory / ".git").is_dir():
                update.repository(directory)
        update.new_repositories()
        print(update.write_report(), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
