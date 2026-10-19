"""Tools at their pinned versions, and Docker."""

import json
import shutil
from collections.abc import Iterator

from doctor.commands import run, succeeds
from doctor.results import Result
from doctor.settings import HOME, WORKSPACE, workspace_repositories


def missing_tools(listing: dict) -> list[str]:
    """Tools a mise.toml pins that are not installed, from `mise ls --current --json`."""
    return sorted(
        f"{tool}@{version.get('requested_version') or version.get('version')}"
        for tool, versions in listing.items()
        for version in versions
        if not version.get("installed")
    )


def check() -> Iterator[Result]:
    section = "Tools"
    for tool in ("git", "gh", "mise", "docker"):
        installed = shutil.which(tool) is not None or (HOME / ".local" / "bin" / tool).exists()
        yield Result(section, f"{tool} is installed", installed, "Run setup.sh again.")
    mise = shutil.which("mise") or str(HOME / ".local" / "bin" / "mise")
    missing = []
    for directory in [WORKSPACE, *workspace_repositories()]:
        if not (directory / "mise.toml").exists():
            continue
        listed = run([mise, "ls", "--current", "--json"], cwd=directory)
        try:
            tools = missing_tools(json.loads(listed.stdout or "{}"))
        except json.JSONDecodeError:
            tools = ["(mise could not read its configuration)"]
        missing += [f"{directory.name}: {tool}" for tool in tools]
    yield Result(
        section,
        "every tool is installed at its pinned version",
        not missing,
        "Run mise install in the folder named, or mise run doctor -- --fix.",
        "tools",
        missing,
    )

    docker_up = succeeds(["docker", "info"])
    yield Result(section, "Docker daemon is reachable", docker_up, "Start Docker.", "docker")
    yield Result(
        section,
        "Docker Compose is available",
        succeeds(["docker", "compose", "version"]),
        "Run setup.sh again.",
    )
    runs = docker_up and succeeds(["docker", "run", "--rm", "hello-world"], timeout=120)
    yield Result(
        section,
        "Docker runs a container",
        runs,
        "Check `docker run --rm hello-world`; Docker Hub must be reachable through the firewall.",
    )
