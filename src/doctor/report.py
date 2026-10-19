"""The results as readable text, or as one JSON document."""

import json
import os
import sys
from dataclasses import asdict

from doctor.results import Result
from doctor.settings import UPDATE_REPORT_FILE


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


def as_json(results: list[Result], made: list[dict]) -> str:
    failures = sum(result.ok is False for result in results)
    return json.dumps(
        {"checks": [asdict(result) for result in results], "repairs": made, "failures": failures}, indent=2
    )
