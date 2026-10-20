"""The workspace: its files, clones, git hooks, the playbook and the background update."""

import shutil
from collections.abc import Iterator

from doctor.checks.github_data import convention_repositories
from doctor.commands import run, succeeds
from doctor.results import Result
from doctor.settings import HANDBOOK_DATA, HOME, REPOSITORY, SKILLS_DIR, WORKSPACE, workspace_repositories


def check() -> Iterator[Result]:
    section = "Workspace"
    for name in ("AGENTS.md", "mise.toml"):
        yield Result(
            section,
            f"workspace {name} exists",
            (WORKSPACE / name).exists(),
            "Run mise run doctor -- --fix.",
            "workspace-files",
        )
    yield Result(
        section,
        "the handbook is cloned",
        (WORKSPACE / "handbook" / ".git").is_dir(),
        "Run mise run doctor -- --fix.",
        "clone",
    )
    if HANDBOOK_DATA.is_dir():
        try:
            expected = {repository.name for repository in convention_repositories()}
            cloned = {directory.name for directory in workspace_repositories()}
            missing = sorted(expected - cloned)
            yield Result(
                section,
                "every organization repository is cloned",
                not missing,
                "Run mise run doctor -- --fix.",
                "clone",
                missing,
            )
        except RuntimeError, FileNotFoundError:
            pass

    without_hooks, behind = [], []
    for directory in workspace_repositories():
        hooks = run(["git", "-C", str(directory), "config", "core.hooksPath"]).stdout.strip()
        if hooks != str(REPOSITORY / "hooks"):
            without_hooks.append(directory.name)
        branch = run(
            ["git", "-C", str(directory), "symbolic-ref", "--short", "--quiet", "HEAD"]
        ).stdout.strip()
        count = run(["git", "-C", str(directory), "rev-list", "--count", "main..origin/main"]).stdout.strip()
        if branch == "main" and count.isdigit() and int(count) > 0:
            behind.append(directory.name)
    yield Result(
        section,
        "every workspace repository uses the organization's git hooks",
        not without_hooks,
        "Run mise run doctor -- --fix.",
        "hooks",
        without_hooks,
    )
    yield Result(
        section,
        "no checked-out main is behind GitHub",
        not behind,
        "Run mise run update; .workspace-update.md says why a repository was not updated.",
        details=behind,
    )
    playbook = shutil.which("playbook") is not None or (HOME / ".local" / "bin" / "playbook").exists()
    yield Result(
        section, "the playbook command is installed", playbook, "Run mise run doctor -- --fix.", "playbook"
    )
    skills = any(SKILLS_DIR.glob("bytelibrary-*/SKILL.md"))
    yield Result(
        section,
        f"the playbook's skills are in {SKILLS_DIR}",
        skills,
        "Run mise run doctor -- --fix.",
        "playbook",
    )
    # Where there are no user services (some containers and CI runners), setup cannot schedule it either.
    if run(["systemctl", "--user", "is-system-running"]).stdout.strip() in ("running", "degraded"):
        scheduled = succeeds(["systemctl", "--user", "is-active", "--quiet", "bytelibrary-update.timer"])
        yield Result(
            section,
            "the background update is scheduled",
            scheduled,
            "Run mise run doctor -- --fix.",
            "updates",
        )
