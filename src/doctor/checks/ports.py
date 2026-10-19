"""Local ports, against the handbook's port data."""

import re
from collections.abc import Iterator

from doctor.commands import run
from doctor.handbook import rows
from doctor.results import Result
from doctor.settings import HANDBOOK_DATA, SHARED_COMPONENTS_OWNER


def port_owners(ranges: list[dict], repositories: list[dict]) -> dict[int, str]:
    """Which repository each recorded port belongs to: the shared range, and each service's block."""
    owners = {}
    for port_range in ranges:
        if port_range["code"] == "shared-components":
            owners.update(
                dict.fromkeys(range(port_range["first"], port_range["last"] + 1), SHARED_COMPONENTS_OWNER)
            )
    for repository in repositories:
        if repository.get("port_block") is not None:
            block = repository["port_block"]
            owners.update(dict.fromkeys(range(block, block + 10), repository["name"]))
    return owners


def listening_ports(ss_output: str) -> set[int]:
    """TCP ports something listens on, from `ss --listening --tcp --numeric --no-header`."""
    ports = set()
    for line in ss_output.splitlines():
        columns = line.split()
        if len(columns) >= 4 and (match := re.search(r":(\d+)$", columns[3])):
            ports.add(int(match.group(1)))
    return ports


def container_ports(docker_output: str) -> dict[int, tuple[str, str]]:
    """Published ports, each with its container and Compose project, from `docker ps` in the format
    `{{.Names}}\\t{{.Label "com.docker.compose.project"}}\\t{{.Ports}}`."""
    published = {}
    for line in docker_output.splitlines():
        name, project, ports = (line.split("\t") + ["", ""])[:3]
        for port in re.findall(r":(\d+)->", ports):
            published[int(port)] = (name, project)
    return published


def port_problems(
    owners: dict[int, str], listening: set[int], published: dict[int, tuple[str, str]]
) -> list[str]:
    problems = []
    for port in sorted(listening & owners.keys()):
        owner = owners[port]
        if port not in published:
            problems.append(
                f"{port} ({owner}'s ports) is used by a process outside Docker: see sudo ss -ltnp"
            )
        elif published[port][1] != owner:
            name, project = published[port]
            problems.append(
                f"{port} ({owner}'s ports) is used by container {name}"
                f"{f' of project {project}' if project else ''}: docker stop {name}"
            )
    return problems


def check() -> Iterator[Result]:
    section = "Local ports"
    if not HANDBOOK_DATA.is_dir():
        yield Result(
            section,
            "the handbook is not cloned, so ports cannot be checked",
            False,
            "Run mise run doctor -- --fix.",
            "clone",
        )
        return
    owners = port_owners(rows("port-ranges"), rows("repositories"))
    listening = listening_ports(run(["ss", "--listening", "--tcp", "--numeric", "--no-header"]).stdout)
    docker = run(
        ["docker", "ps", "--format", '{{.Names}}\t{{.Label "com.docker.compose.project"}}\t{{.Ports}}']
    )
    problems = port_problems(owners, listening, container_ports(docker.stdout))
    yield Result(
        section,
        "the recorded ports are free or used by their repository's containers",
        not problems,
        "Stop what holds the port, as described; the doctor never stops it.",
        details=problems,
    )
