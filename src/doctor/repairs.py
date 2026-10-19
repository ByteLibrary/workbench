"""What --fix repairs: only what is safe to repair, by running setup's steps again."""

import sys

from doctor.commands import succeeds
from doctor.results import Result
from doctor.settings import REPOSITORY, WORKSPACE


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
