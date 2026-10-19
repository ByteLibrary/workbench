#!/usr/bin/python3
"""Checks that the development machine and the workspace are set up correctly: tools, Docker, the
firewall, credentials, local ports, GitHub access, the handbook's data against GitHub, repository
settings and the workspace. Says how to fix each problem; with --fix, repairs what is safe to repair
and checks again. Exits with 1 if any check fails. Safe to run at any time.

Usage: mise run doctor [-- --fix] [--dry-run] [--json] [--quiet] [--verbose]

Examples:
  mise run doctor                       check everything
  mise run doctor -- --fix --dry-run    list the repairs --fix would make
  mise run doctor -- --fix              repair what is safe to repair, then check again
"""

# The system's Python, which has PyYAML (install-system-packages.sh); mise's Python may not.

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

ORGANIZATION = "ByteLibrary"
PROJECT_NUMBER = 1
HOME = Path.home()
REPOSITORY = Path(__file__).resolve().parent.parent
WORKSPACE = Path(os.environ.get("BYTELIBRARY_WORKSPACE_DIR", HOME / "ByteLibrary"))
GH_CONFIG_DIR_SCOPED = Path(os.environ.get("BYTELIBRARY_GH_CONFIG_DIR", HOME / ".config" / "gh-bytelibrary"))
WORKSPACE_GITCONFIG = HOME / ".gitconfig-bytelibrary"
GIT_CREDENTIALS_FILE = Path(
    os.environ.get("BYTELIBRARY_GIT_CREDENTIALS_FILE", HOME / ".config" / "bytelibrary" / "git-credentials")
)
HANDBOOK_DATA = Path(os.environ.get("BYTELIBRARY_HANDBOOK_DATA_DIR", WORKSPACE / "handbook" / "data"))
UPDATE_REPORT_FILE = WORKSPACE / ".workspace-update.md"
SKILLS_DIR = Path(os.environ.get("PLAYBOOK_SKILLS_DIR", HOME / ".agents" / "skills"))
# Setup without questions, as in CI: a token instead of a person's sign-in (lib.sh).
NON_INTERACTIVE = bool(os.environ.get("BYTELIBRARY_GITHUB_TOKEN"))
# Shared components' ports belong to the repository that defines them (ADR-0023).
SHARED_COMPONENTS_OWNER = "deployments"

VERBOSE = False


@dataclass
class Result:
    section: str
    name: str
    # True passed, False failed, None information only.
    ok: bool | None
    fix: str = ""
    # The repair --fix makes for this failure, if it is safe to make.
    repair: str | None = None
    details: list[str] = field(default_factory=list)


# The repairs --fix makes: a description and the commands, each run from the workspace.
def repairs() -> dict[str, tuple[str, list[list[str]]]]:
    scripts = REPOSITORY / "scripts"
    return {
        "tools": ("install the pinned tools", [[str(scripts / "install-tools.sh"), "repositories"]]),
        "firewall": (
            "apply the site allowlist again",
            [
                ["sudo", "systemctl", "enable", "--now", "bytelibrary-firewall.path"],
                ["sudo", "systemctl", "restart", "bytelibrary-firewall.service"],
            ],
        ),
        "docker": ("start Docker", [["sudo", "systemctl", "start", "docker"]]),
        "hooks": ("set the organization's git hooks", [[str(scripts / "configure-git-hooks.sh")]]),
        "workspace-files": ("write the workspace files", [[str(scripts / "write-workspace-files.sh")]]),
        "updates": ("schedule the background update", [[str(scripts / "configure-updates.sh")]]),
        "clone": ("clone the missing repositories", [[str(scripts / "clone-repositories.sh")]]),
        "playbook": ("install the playbook", [[str(scripts / "install-playbook.sh")]]),
    }


def run(command: list[str], cwd: Path | None = None, environment: dict | None = None, timeout: int = 60):
    if VERBOSE:
        print(f"==> {' '.join(command)}", file=sys.stderr)
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env={**os.environ, **(environment or {})},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(command, 127, "", str(error))


def succeeds(command: list[str], **options) -> bool:
    return run(command, **options).returncode == 0


def gh(*arguments: str) -> subprocess.CompletedProcess:
    """gh with the ByteLibrary-only login, or with the token when running without questions."""
    if NON_INTERACTIVE:
        return run(["gh", *arguments], environment={"GH_TOKEN": os.environ["BYTELIBRARY_GITHUB_TOKEN"]})
    return run(["gh", *arguments], environment={"GH_CONFIG_DIR": str(GH_CONFIG_DIR_SCOPED)})


def gh_json(*arguments: str):
    completed = gh(*arguments)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "gh failed")
    return json.loads(completed.stdout) if completed.stdout.strip() else None


def rows(table: str) -> list[dict]:
    return yaml.safe_load((HANDBOOK_DATA / f"{table}.yaml").read_text(encoding="utf-8")) or []


def workspace_repositories() -> list[Path]:
    return sorted(directory for directory in WORKSPACE.iterdir() if (directory / ".git").is_dir())


# Tools and Docker ------------------------------------------------------------------------------------


def missing_tools(listing: dict) -> list[str]:
    """Tools a mise.toml pins that are not installed, from `mise ls --current --json`."""
    return sorted(
        f"{tool}@{version.get('requested_version') or version.get('version')}"
        for tool, versions in listing.items()
        for version in versions
        if not version.get("installed")
    )


def check_tools() -> Iterator[Result]:
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


# The firewall ----------------------------------------------------------------------------------------


def check_firewall() -> Iterator[Result]:
    section = "Firewall"
    active = succeeds(
        ["systemctl", "is-active", "--quiet", "bytelibrary-dns.service", "bytelibrary-firewall.path"]
    )
    yield Result(section, "the site allowlist is active", active, "Run mise run doctor -- --fix.", "firewall")
    reachable = succeeds(["curl", "-fsS", "-o", "/dev/null", "--max-time", "15", "https://github.com"])
    yield Result(
        section, "an allowed site is reachable (github.com)", reachable, "Check the network and the firewall."
    )
    blocked = not succeeds(["curl", "-sS", "-o", "/dev/null", "--max-time", "10", "https://example.com"])
    yield Result(
        section,
        "a site not on the allowlist is blocked (example.com)",
        blocked,
        "Run mise run doctor -- --fix.",
        "firewall",
    )
    mounts = run(["findmnt", "--types", "fuse.sshfs", "--noheadings", "--output", "TARGET"]).stdout.split()
    yield Result(
        section,
        "no folder of your computer is mounted in the machine",
        not mounts,
        "On your computer: multipass umount bytelibrary.",
        details=mounts,
    )
    recent = run([str(REPOSITORY / "scripts" / "firewall.sh"), "blocked"]).stdout.strip().splitlines()
    if recent:
        yield Result(
            section, f"{len(recent)} site(s) were blocked in the last day: mise run firewall:blocked", None
        )


# Credentials ---------------------------------------------------------------------------------------


def stray_credentials(home: Path, environment: dict) -> list[str]:
    """Credentials besides the ByteLibrary sign-in. Agent tools' own folders are never looked at."""
    found = []
    hosts = home / ".config" / "gh" / "hosts.yml"
    if hosts.exists() and hosts.read_text(encoding="utf-8").strip() not in ("", "{}"):
        found.append(f"a gh login outside the workspace ({hosts}): gh auth logout, then delete the file")
    if (home / ".git-credentials").exists() and (home / ".git-credentials").read_text().strip():
        found.append(f"stored git credentials ({home / '.git-credentials'}): delete the file")
    for variable in ("GH_TOKEN", "GITHUB_TOKEN"):
        if environment.get(variable):
            found.append(f"{variable} is set: remove it from your shell's settings")
    ssh = home / ".ssh"
    if ssh.is_dir():
        for path in sorted(ssh.iterdir()):
            if path.is_file() and "PRIVATE KEY" in path.read_text(errors="ignore")[:200]:
                found.append(f"a private SSH key ({path}): the machine needs none; delete it")
    for path, what in (
        (home / ".aws" / "credentials", "AWS credentials"),
        (home / ".config" / "gcloud" / "credentials.db", "Google Cloud credentials"),
        (home / ".config" / "gcloud" / "application_default_credentials.json", "Google Cloud credentials"),
        (home / ".azure" / "msal_token_cache.json", "Azure credentials"),
        (home / ".azure" / "accessTokens.json", "Azure credentials"),
    ):
        if path.exists():
            found.append(f"{what} ({path}): no cloud is set up here; delete it")
    docker = home / ".docker" / "config.json"
    if docker.exists():
        try:
            logins = [
                registry
                for registry, entry in json.loads(docker.read_text()).get("auths", {}).items()
                if entry
            ]
        except (json.JSONDecodeError, AttributeError):
            logins = []
        if logins:
            found.append(f"Docker registry logins ({', '.join(logins)}): docker logout <registry>")
    npmrc = home / ".npmrc"
    if npmrc.exists() and re.search(r"_auth(Token)?\s*=", npmrc.read_text()):
        found.append(f"an npm token ({npmrc}): remove its _authToken line")
    pypirc = home / ".pypirc"
    if pypirc.exists() and re.search(r"^\s*password\s*=", pypirc.read_text(), re.MULTILINE):
        found.append(f"a package index password ({pypirc}): remove it")
    return found


def check_credentials() -> Iterator[Result]:
    section = "Credentials"
    found = stray_credentials(HOME, dict(os.environ))
    yield Result(
        section,
        "no credentials besides the ByteLibrary sign-in and your agent CLI's",
        not found,
        "Remove each one as described; the doctor never deletes credentials.",
        details=found,
    )
    helper = run(
        ["git", "config", "--global", "--get-all", "credential.https://github.com.helper"]
    ).stdout.strip()
    yield Result(
        section,
        "GitHub credentials are not configured outside the workspace",
        not helper,
        "Run setup.sh again.",
    )


# Local ports -----------------------------------------------------------------------------------------


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


def check_ports() -> Iterator[Result]:
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


# GitHub access, settings and the handbook's data -----------------------------------------------------


def check_github_access() -> Iterator[Result]:
    section = "GitHub access"
    if NON_INTERACTIVE:
        yield Result(section, "skipped without questions: the checks of a person's sign-in", None)
    else:
        yield Result(
            section,
            "gh is logged in, in its ByteLibrary-only configuration",
            gh("auth", "status", "--hostname", "github.com").returncode == 0,
            "Run mise run sign-in.",
        )
        token = gh("auth", "token").stdout.strip()
        yield Result(
            section,
            "signed in through the ByteLibrary Developer Access App",
            token.startswith("ghu_"),
            "Run mise run sign-in.",
        )
        outside = gh(
            "api",
            "--paginate",
            "/user/repos",
            "--jq",
            f'.[] | select(.private and .owner.login != "{ORGANIZATION}") | .full_name',
        ).stdout.split()
        yield Result(
            section,
            f"the sign-in reaches no private repositories outside {ORGANIZATION}",
            not outside,
            "Sign in through the App (mise run sign-in), not with a personal token.",
            details=outside,
        )
    helper = run(
        ["git", "-C", str(REPOSITORY), "config", "--get-all", "credential.https://github.com.helper"]
    ).stdout
    private = (
        GIT_CREDENTIALS_FILE.exists()
        and GIT_CREDENTIALS_FILE.stat().st_size > 0
        and (GIT_CREDENTIALS_FILE.stat().st_mode & 0o777 == 0o600)
    )
    yield Result(
        section,
        "workspace repositories authenticate with the sign-in, from a private file",
        private and f"store --file={GIT_CREDENTIALS_FILE}" in helper.splitlines(),
        "Run mise run sign-in.",
    )
    origin = run(["git", "-C", str(REPOSITORY), "config", "--show-origin", "user.email"]).stdout
    yield Result(
        section, "workspace commit identity is set", str(WORKSPACE_GITCONFIG) in origin, "Run setup.sh again."
    )


def convention_repositories() -> list[dict]:
    kinds = {kind["code"] for kind in rows("repository-kinds")}
    repositories = gh_json("api", "--paginate", f"orgs/{ORGANIZATION}/repos?per_page=100") or []
    return [r for r in repositories if not r["archived"] and kinds & set(r.get("topics") or [])]


def merge_settings(repository: dict) -> str:
    if repository.get("allow_squash_merge") is None:
        return "unreadable"
    expected = (
        repository["allow_squash_merge"]
        and not repository["allow_merge_commit"]
        and not repository["allow_rebase_merge"]
        and repository.get("squash_merge_commit_title") == "PR_TITLE"
        and repository.get("squash_merge_commit_message") == "PR_BODY"
        and repository.get("delete_branch_on_merge")
    )
    return "ok" if expected else "drift"


def repository_differences(documented: list[dict], on_github: list[dict], kinds: set[str]) -> list[str]:
    """Differences between the handbook's repositories and GitHub's, in both directions."""
    github = {repository["name"]: repository for repository in on_github if not repository["archived"]}
    problems = []
    for entry in documented:
        name = entry["name"]
        if entry["status"] == "planned":
            if name in github:
                problems.append(f"{name} exists on GitHub but is planned in the handbook")
            continue
        if name not in github:
            problems.append(f"{name} is active in the handbook but does not exist on GitHub")
            continue
        repository = github[name]
        expected_topics = sorted(
            [entry["kind"]]
            + ([f"context-{entry['context']}"] if entry.get("context") else [])
            + ([f"language-{entry['language']}"] if entry.get("language") else [])
        )
        differences = []
        if repository["visibility"] != entry["visibility"]:
            differences.append(
                f"visibility is {repository['visibility']}, the handbook says {entry['visibility']}"
            )
        if (repository.get("description") or "") != entry["description"]:
            differences.append("description differs from the handbook")
        if sorted(repository.get("topics") or []) != expected_topics:
            differences.append(
                f"topics are {sorted(repository.get('topics') or [])}, the handbook implies {expected_topics}"
            )
        if differences:
            problems.append(f"{name}: {'; '.join(differences)}")
    named = {entry["name"] for entry in documented}
    for name, repository in github.items():
        if name not in named and kinds & set(repository.get("topics") or []):
            problems.append(f"{name} follows the conventions on GitHub but is missing from the handbook")
    return problems


def check_github_data() -> Iterator[Result]:
    if not HANDBOOK_DATA.is_dir():
        yield Result(
            "Handbook data matches GitHub",
            "the handbook is not cloned, so its data cannot be compared with GitHub",
            False,
            "Run mise run doctor -- --fix.",
            "clone",
        )
        return
    try:
        repositories = gh_json("api", "--paginate", f"orgs/{ORGANIZATION}/repos?per_page=100") or []
        kinds = {kind["code"] for kind in rows("repository-kinds")}
        convention = [r for r in repositories if not r["archived"] and kinds & set(r.get("topics") or [])]
    except RuntimeError as error:
        yield Result(
            "Handbook data matches GitHub",
            f"GitHub could not be read: {error}",
            False,
            "Run mise run sign-in.",
        )
        return

    section = "Repository settings"
    for repository in convention:
        state = merge_settings(gh_json("api", f"repos/{ORGANIZATION}/{repository['name']}") or {})
        if state == "unreadable":
            yield Result(
                section, f"{repository['name']}: settings not visible without administration access", None
            )
        else:
            yield Result(
                section,
                f"{repository['name']}: repository settings",
                state == "ok",
                "Set squash merges only, with the pull request's title and description, "
                "and delete merged branches.",
            )

    section = "Handbook data matches GitHub"
    problems = repository_differences(rows("repositories"), repositories, kinds)
    yield Result(
        section,
        "the handbook's repositories match GitHub",
        not problems,
        "Correct GitHub or data/repositories.yaml in the handbook.",
        details=problems,
    )
    expected = {context["code"] for context in rows("contexts")} | {"organization"}
    query = """query($organization: String!, $number: Int!) {
      organization(login: $organization) { projectV2(number: $number) { field(name: "Context") {
        ... on ProjectV2SingleSelectField { options { name } } } } } }"""
    data = gh_json(
        "api",
        "graphql",
        "-F",
        f"number={PROJECT_NUMBER}",
        "-f",
        f"organization={ORGANIZATION}",
        "-f",
        f"query={query}",
    )
    actual = {option["name"] for option in data["data"]["organization"]["projectV2"]["field"]["options"]}
    yield Result(
        section,
        "the project's Context options match the handbook's contexts",
        expected == actual,
        "Correct the project's Context field or data/contexts.yaml in the handbook.",
        details=[f"missing: {', '.join(sorted(expected - actual))}"] * bool(expected - actual)
        + [f"not in the handbook: {', '.join(sorted(actual - expected))}"] * bool(actual - expected),
    )


# The workspace -------------------------------------------------------------------------------------


def check_workspace() -> Iterator[Result]:
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
            expected = {repository["name"] for repository in convention_repositories()}
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
        except (RuntimeError, FileNotFoundError):
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


CHECKS: list[Callable[[], Iterator[Result]]] = [
    check_tools,
    check_firewall,
    check_credentials,
    check_ports,
    check_github_access,
    check_github_data,
    check_workspace,
]


def check_everything() -> list[Result]:
    results = []
    for check in CHECKS:
        try:
            results += list(check())
        except Exception as error:  # A broken check is a failure to report, not a crash.
            results.append(
                Result(check.__name__.removeprefix("check_"), f"the check could not run: {error}", False)
            )
    return results


def make_repairs(results: list[Result], dry_run: bool) -> list[dict]:
    known = repairs()
    wanted = list(dict.fromkeys(result.repair for result in results if result.ok is False and result.repair))
    made = []
    for key in wanted:
        description, commands = known[key]
        if dry_run:
            made.append({"repair": description, "done": False})
            continue
        print(f"==> Repairing: {description}", file=sys.stderr)
        done = all(succeeds(command, cwd=WORKSPACE, timeout=900) for command in commands)
        made.append({"repair": description, "done": done})
    return made


def report(results: list[Result], made: list[dict], quiet: bool, dry_run: bool) -> None:
    section = None
    for result in results:
        if quiet and result.ok is not False:
            continue
        if result.section != section:
            section = result.section
            print(f"==> {section}")
        mark = {True: "\033[32m ok\033[0m", False: "\033[33m !!\033[0m", None: "\033[34m==>\033[0m"}[
            result.ok
        ]
        if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
            mark = {True: " ok", False: " !!", None: "==>"}[result.ok]
        print(f"{mark} {result.name}")
        for detail in result.details:
            print(f"      {detail}")
        if result.ok is False and result.fix:
            print(f"      Fix: {result.fix}")
    if made:
        print(f"==> Repairs{' --fix would make' if dry_run else ''}")
        for repair in made:
            print(f"    {repair['repair']}{'' if dry_run else (': done' if repair['done'] else ': failed')}")
    if not quiet and UPDATE_REPORT_FILE.exists() and UPDATE_REPORT_FILE.stat().st_size:
        print("==> Workspace updates")
        for line in UPDATE_REPORT_FILE.read_text().splitlines():
            print(f"    {line}")
    failures = sum(result.ok is False for result in results)
    print(
        f"ERR {failures} check(s) failed. See README.md, Troubleshooting."
        if failures
        else " ok Workspace is ready"
    )


def main(argv: list[str] | None = None) -> int:
    global VERBOSE
    parser = argparse.ArgumentParser(
        prog="mise run doctor --",
        description=__doc__.split("\n\n")[0].replace("\n", " "),
        epilog="Examples:\n"
        "  mise run doctor\n  mise run doctor -- --fix --dry-run\n  mise run doctor -- --fix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--fix", action="store_true", help="repair what is safe to repair, then check again")
    parser.add_argument("--dry-run", action="store_true", help="with --fix: list the repairs, change nothing")
    parser.add_argument("--json", action="store_true", help="print the results as one JSON document")
    parser.add_argument("--quiet", action="store_true", help="show only the checks that failed")
    parser.add_argument("--verbose", action="store_true", help="show each command a check runs, on stderr")
    arguments = parser.parse_args(argv)
    VERBOSE = arguments.verbose

    results = check_everything()
    made = []
    if arguments.fix:
        made = make_repairs(results, arguments.dry_run)
        if made and not arguments.dry_run:
            results = check_everything()
    failures = sum(result.ok is False for result in results)
    if arguments.json:
        document = {"checks": [asdict(result) for result in results], "repairs": made, "failures": failures}
        print(json.dumps(document, indent=2))
    else:
        report(results, made, arguments.quiet, arguments.fix and arguments.dry_run)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
