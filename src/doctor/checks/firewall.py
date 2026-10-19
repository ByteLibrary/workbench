"""The site allowlist, and folders of the developer's computer mounted in the machine."""

from collections.abc import Iterator

from doctor.commands import run, succeeds
from doctor.results import Result
from doctor.settings import REPOSITORY


def check() -> Iterator[Result]:
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
