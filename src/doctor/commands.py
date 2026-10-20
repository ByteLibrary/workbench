"""Running other programs: git, gh, docker and the rest. Checks never call subprocess themselves."""

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

from doctor.settings import GH_CONFIG_DIR_SCOPED, NON_INTERACTIVE

# Set by --verbose: print each command on stderr before running it.
verbose = False


def run(
    command: list[str],
    cwd: Path | None = None,
    environment: Mapping[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    if verbose:
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


def succeeds(command: list[str], cwd: Path | None = None, timeout: int = 60) -> bool:
    return run(command, cwd=cwd, timeout=timeout).returncode == 0


def gh(*arguments: str) -> subprocess.CompletedProcess[str]:
    """gh with the ByteLibrary-only login, or with the token when running without questions."""
    if NON_INTERACTIVE:
        return run(["gh", *arguments], environment={"GH_TOKEN": os.environ["BYTELIBRARY_GITHUB_TOKEN"]})
    return run(["gh", *arguments], environment={"GH_CONFIG_DIR": str(GH_CONFIG_DIR_SCOPED)})


def gh_json(*arguments: str) -> object:
    """gh's JSON output, for a model to read; None when gh printed nothing."""
    completed = gh(*arguments)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "gh failed")
    return json.loads(completed.stdout) if completed.stdout.strip() else None
