#!/usr/bin/env python3
"""Prints facts from the handbook's data tables, one record per line, for the shell scripts.

Fields are separated by the ASCII unit separator (\\x1f), not tabs: bash collapses consecutive tabs, which
would shift the fields after an empty one.

Usage: handbook_data.py <handbook data directory> kinds|contexts|repositories
"""
import pathlib
import sys

import yaml


def rows(directory, table):
    return yaml.safe_load((pathlib.Path(directory) / f"{table}.yaml").read_text(encoding="utf-8")) or []


def main():
    if len(sys.argv) != 3 or sys.argv[2] not in ("kinds", "contexts", "repositories"):
        sys.exit(__doc__)
    directory, query = sys.argv[1], sys.argv[2]
    if query == "kinds":
        lines = [kind["code"] for kind in rows(directory, "repository-kinds")]
    elif query == "contexts":
        lines = [context["code"] for context in rows(directory, "contexts")]
    else:
        lines = [
            "\x1f".join([repository["name"], repository["status"], repository["visibility"], repository["kind"],
                       repository.get("context") or "", repository.get("language") or "", repository["description"]])
            for repository in rows(directory, "repositories")
        ]
    print("\n".join(lines))


if __name__ == "__main__":
    main()
