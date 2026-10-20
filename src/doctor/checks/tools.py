"""Tools at their pinned versions, and Docker."""

import shutil
from collections.abc import Iterator

from pydantic import TypeAdapter, ValidationError

from doctor.commands import run, succeeds
from doctor.outside import Outside
from doctor.results import Result
from doctor.settings import HOME, WORKSPACE, workspace_repositories


class MiseVersion(Outside):
    version: str | None = None
    requested_version: str | None = None
    installed: bool = False


# `mise ls --current --json`: each tool with its pinned versions.
MISE_LISTING = TypeAdapter(dict[str, list[MiseVersion]])


def missing_tools(listing: dict[str, list[MiseVersion]]) -> list[str]:
    """Tools a mise.toml pins that are not installed."""
    return sorted(
        f"{tool}@{version.requested_version or version.version}"
        for tool, versions in listing.items()
        for version in versions
        if not version.installed
    )


def check() -> Iterator[Result]:
    section = "Tools"
    for tool in ("git", "gh", "mise", "docker"):
        installed = shutil.which(tool) is not None or (HOME / ".local" / "bin" / tool).exists()
        yield Result(section, f"{tool} is installed", installed, "Run setup.sh again.")
    mise = shutil.which("mise") or str(HOME / ".local" / "bin" / "mise")
    missing: list[str] = []
    for directory in [WORKSPACE, *workspace_repositories()]:
        if not (directory / "mise.toml").exists():
            continue
        listed = run([mise, "ls", "--current", "--json"], cwd=directory)
        try:
            tools = missing_tools(MISE_LISTING.validate_json(listed.stdout or "{}"))
        except ValidationError:
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
