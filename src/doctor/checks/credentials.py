"""Credentials besides the ByteLibrary sign-in and the developer's agent CLI's."""

import json
import os
import re
from collections.abc import Iterator
from pathlib import Path

from doctor.commands import run
from doctor.results import Result
from doctor.settings import HOME


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
        except json.JSONDecodeError, AttributeError:
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


def check() -> Iterator[Result]:
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
