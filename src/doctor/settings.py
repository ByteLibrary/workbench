"""Where things are on the development machine, the same settings as workbench's scripts/lib.sh."""

import os
from pathlib import Path

ORGANIZATION = "ByteLibrary"
PROJECT_NUMBER = 1
HOME = Path.home()
# The workbench clone: this package is src/doctor in it.
REPOSITORY = Path(__file__).resolve().parents[2]
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


def workspace_repositories() -> list[Path]:
    return sorted(directory for directory in WORKSPACE.iterdir() if (directory / ".git").is_dir())
