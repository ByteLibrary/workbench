"""Checks that the development machine and the workspace are set up correctly: tools, Docker, the
firewall, credentials, local ports, GitHub access, the handbook's data against GitHub, repository
settings and the workspace. Says how to fix each problem; with --fix, repairs what is safe to repair
and checks again. Exits with 1 if any check fails. Safe to run at any time.

Usage: mise run doctor [-- --fix] [--dry-run] [--json] [--quiet] [--verbose]

Examples:
  mise run doctor                       check everything
  mise run doctor -- --fix --dry-run    list the repairs --fix would make
  mise run doctor -- --fix              repair what is safe to repair, then check again
  mise run doctor -- --skip credentials leave out a group of checks, on a machine that is not a
                                        development machine
"""

import argparse
import os

from doctor import commands
from doctor.checks import CHECKS, check_everything
from doctor.repairs import make_repairs
from doctor.report import as_json, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mise run doctor --",
        description=__doc__.split("\n\n")[0].replace("\n", " "),
        epilog="Examples:\n"
        "  mise run doctor\n  mise run doctor -- --fix --dry-run\n  mise run doctor -- --fix\n"
        "  mise run doctor -- --skip credentials",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--fix", action="store_true", help="repair what is safe to repair, then check again")
    parser.add_argument("--dry-run", action="store_true", help="with --fix: list the repairs, change nothing")
    parser.add_argument("--json", action="store_true", help="print the results as one JSON document")
    parser.add_argument("--quiet", action="store_true", help="show only the checks that failed")
    parser.add_argument("--verbose", action="store_true", help="show each command a check runs, on stderr")
    parser.add_argument(
        "--skip",
        action="append",
        # Setup runs the doctor itself, so CI passes groups to skip through BYTELIBRARY_DOCTOR_SKIP.
        default=os.environ.get("BYTELIBRARY_DOCTOR_SKIP", "").split(),
        choices=list(CHECKS),
        metavar="CHECK",
        help="leave out a group of checks (repeatable), e.g. on a machine that is not a development machine: "
        + ", ".join(CHECKS),
    )
    arguments = parser.parse_args(argv)
    unknown = sorted(set(arguments.skip) - CHECKS.keys())
    if unknown:
        parser.error(f"BYTELIBRARY_DOCTOR_SKIP names unknown checks: {', '.join(unknown)}")
    commands.verbose = arguments.verbose

    results = check_everything(arguments.skip)
    made = []
    if arguments.fix:
        made = make_repairs(results, arguments.dry_run)
        if made and not arguments.dry_run:
            results = check_everything(arguments.skip)
    failures = sum(result.ok is False for result in results)
    if arguments.json:
        print(as_json(results, made))
    else:
        report(results, made, arguments.quiet, arguments.fix and arguments.dry_run)
    return 1 if failures else 0
