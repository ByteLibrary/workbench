#!/usr/bin/env python3
"""Prints facts from the handbook's data tables, one record per line, for the shell scripts.

Fields are separated by the ASCII unit separator (\\x1f), not tabs: bash collapses consecutive tabs, which
would shift the fields after an empty one. Runs on the system's Python, with its own PyYAML.

Example:
  handbook_data.py ~/ByteLibrary/handbook/data kinds
"""

import argparse
import pathlib
import sys
from typing import Any

import yaml


def rows(directory: str, table: str) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = (
        yaml.safe_load((pathlib.Path(directory) / f"{table}.yaml").read_text(encoding="utf-8")) or []
    )
    return loaded


def main(argv: list[str]) -> int:
    description, epilog = __doc__.split("\n\n", 1)
    parser = argparse.ArgumentParser(
        prog="handbook_data.py",
        description=description,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("directory", help="the handbook's data folder")
    parser.add_argument("query", choices=("kinds", "contexts", "repositories"), help="what to print")
    arguments = parser.parse_args(argv)
    directory = arguments.directory
    if arguments.query == "kinds":
        lines = [kind["code"] for kind in rows(directory, "repository-kinds")]
    elif arguments.query == "contexts":
        lines = [context["code"] for context in rows(directory, "contexts")]
    else:
        lines = [
            "\x1f".join(
                [
                    repository["name"],
                    repository["status"],
                    repository["visibility"],
                    repository["kind"],
                    repository.get("context") or "",
                    repository.get("language") or "",
                    repository["description"],
                ]
            )
            for repository in rows(directory, "repositories")
        ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
