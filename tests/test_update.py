"""The workspace update, in a throwaway workspace against local bare repositories, with a stand-in for gh
that lists and clones them."""

import fcntl
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "update.py"

FAKE_GH = """#!/usr/bin/env bash
# Stands in for gh: lists the test's repositories and clones them from the local bare repositories.
case "$1" in
  api) printf '%s\\n' $FAKE_REPOSITORIES ;;
  repo) git clone --quiet "$REMOTES/${3#*/}.git" "$4" ;;
esac
"""


class UpdateTest(unittest.TestCase):
    directory: tempfile.TemporaryDirectory[str]
    work: Path
    workspace: Path
    remotes: Path
    environment: dict[str, str]
    report: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.directory = tempfile.TemporaryDirectory()
        work = cls.work = Path(cls.directory.name)
        cls.workspace = work / "ByteLibrary"
        cls.remotes = work / "remotes"
        for folder in (work / "home", cls.remotes, cls.workspace, work / "bin"):
            folder.mkdir()
        (work / "bin" / "gh").write_text(FAKE_GH)
        # Stands in for uv, so the playbook's installer can run without mise.
        (work / "bin" / "uv").write_text("#!/usr/bin/env bash\nexit 0\n")
        for tool in ("gh", "uv"):
            (work / "bin" / tool).chmod(0o755)
        home = Path.home()
        cls.environment = {
            **os.environ,
            # The throwaway home keeps mise's and uv's installs, so workbench's tools are found as pinned.
            "MISE_DATA_DIR": os.environ.get("MISE_DATA_DIR", str(home / ".local" / "share" / "mise")),
            "MISE_STATE_DIR": os.environ.get("MISE_STATE_DIR", str(home / ".local" / "state" / "mise")),
            "MISE_CACHE_DIR": os.environ.get("MISE_CACHE_DIR", str(home / ".cache" / "mise")),
            "UV_CACHE_DIR": os.environ.get("UV_CACHE_DIR", str(home / ".cache" / "uv")),
            "HOME": str(work / "home"),
            "BYTELIBRARY_WORKSPACE_DIR": str(cls.workspace),
            "BYTELIBRARY_UPDATE_LOCK_FILE": str(work / "update.lock"),
            "GIT_CONFIG_GLOBAL": str(work / "home" / ".gitconfig"),
            "REMOTES": str(cls.remotes),
            "FAKE_REPOSITORIES": "alpha beta gamma delta epsilon",
            "PATH": f"{work / 'bin'}{os.pathsep}{os.environ['PATH']}",
        }
        for key, value in (
            ("user.name", "Test"),
            ("user.email", "test@example.com"),
            ("init.defaultBranch", "main"),
        ):
            cls.git("config", "--global", key, value)

        for name in ("handbook", "alpha", "beta", "gamma", "delta", "playbook"):
            cls.remote(name)
        cls.remote("epsilon", clone=False)
        # alpha: main, clean, behind. beta: main with local changes, behind. gamma: a branch whose pull
        # request was merged, behind main. delta: a git operation in progress.
        cls.advance("alpha")
        cls.advance("playbook")
        cls.advance("beta")
        (cls.workspace / "beta" / "README.md").open("a").write("local\n")
        gamma = cls.workspace / "gamma"
        cls.git("-C", str(gamma), "switch", "--quiet", "-c", "feat/1-example")
        cls.git("-C", str(gamma), "push", "--quiet", "-u", "origin", "feat/1-example")
        cls.git("--git-dir", str(cls.remotes / "gamma.git"), "branch", "-D", "feat/1-example")
        cls.advance("gamma")
        cls.advance("delta")
        (cls.workspace / "delta" / ".git" / "index.lock").touch()

        cls.report = cls.update()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.directory.cleanup()

    @classmethod
    def git(cls, *arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments], env=cls.environment, capture_output=True, text=True, check=True
        ).stdout.strip()

    @classmethod
    def remote(cls, name: str, clone: bool = True) -> None:
        """A remote with one commit, and a clone of it in the workspace."""
        bare, seed = cls.remotes / f"{name}.git", cls.work / f"seed-{name}"
        cls.git("init", "--quiet", "--bare", str(bare))
        cls.git("clone", "--quiet", str(bare), str(seed))
        (seed / "README.md").write_text(f"{name}\n")
        if name == "playbook":
            # Stands in for the playbook's installer: records each run.
            installer = seed / "install.sh"
            installer.write_text(f'#!/usr/bin/env bash\necho run >>"{cls.work}/playbook-installs"\n')
            installer.chmod(0o755)
        if name == "handbook":
            (seed / "data").mkdir()
            (seed / "data" / "repository-kinds.yaml").write_text("- code: tooling\n  description: Tools\n")
        cls.git("-C", str(seed), "add", "-A")
        cls.git("-C", str(seed), "commit", "--quiet", "-m", "chore: start")
        cls.git("-C", str(seed), "push", "--quiet", "origin", "main")
        if clone:
            cls.git("clone", "--quiet", str(bare), str(cls.workspace / name))

    @classmethod
    def advance(cls, name: str) -> None:
        """A new commit on the remote's main."""
        seed = cls.work / f"seed-{name}"
        (seed / "README.md").open("a").write("change\n")
        cls.git("-C", str(seed), "commit", "--quiet", "-am", "docs: change")
        cls.git("-C", str(seed), "push", "--quiet", "origin", "main")

    @classmethod
    def update(cls) -> str:
        result = subprocess.run([str(SCRIPT)], env=cls.environment, capture_output=True, text=True)
        return result.stdout + result.stderr

    def head(self, name: str, revision: str = "HEAD") -> str:
        return self.git("-C", str(self.workspace / name), "rev-parse", revision)

    def test_a_clean_main_is_fast_forwarded_and_reported(self) -> None:
        self.assertEqual(self.head("alpha"), self.head("alpha", "origin/main"))
        self.assertIn("alpha: updated, 1 new commit(s)", self.report)

    def test_a_main_with_local_changes_is_left_alone_and_reported(self) -> None:
        self.assertNotEqual(self.head("beta"), self.head("beta", "origin/main"))
        self.assertIn("local", (self.workspace / "beta" / "README.md").read_text())
        self.assertIn("beta: 1 new commit(s) on main, not applied: there are local changes", self.report)

    def test_a_branch_is_never_switched_and_is_reported(self) -> None:
        self.assertEqual(
            self.git("-C", str(self.workspace / "gamma"), "branch", "--show-current"), "feat/1-example"
        )
        self.assertIn("gamma: feat/1-example was merged or deleted on GitHub", self.report)
        self.assertIn("gamma: feat/1-example is 1 commit(s) behind main", self.report)

    def test_a_repository_with_a_git_operation_in_progress_is_skipped(self) -> None:
        self.assertIn("delta: skipped, a git operation is in progress", self.report)

    def test_a_new_repository_is_cloned_reported_and_added_to_the_workspace_files(self) -> None:
        self.assertTrue((self.workspace / "epsilon" / ".git").is_dir())
        self.assertIn("cloned new repositories: epsilon", self.report)
        self.assertIn("epsilon", (self.workspace / "ByteLibrary.code-workspace").read_text())

    def test_a_changed_playbook_is_installed_again_and_reported(self) -> None:
        self.assertTrue((self.work / "playbook-installs").read_text())
        self.assertIn("playbook: installed again", self.report)

    def test_the_report_is_written_for_agents(self) -> None:
        self.assertIn("alpha: updated", (self.workspace / ".workspace-update.md").read_text())

    def test_z_a_second_run_has_nothing_new_for_alpha(self) -> None:
        self.assertNotIn("alpha:", self.update())

    def test_z_a_run_stops_while_another_one_runs(self) -> None:
        with (self.work / "update.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self.assertIn("Another update is running", self.update())


if __name__ == "__main__":
    unittest.main()
