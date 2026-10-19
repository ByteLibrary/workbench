"""The handbook's data tables, which several checks compare the machine and GitHub with."""

import yaml

from doctor.settings import HANDBOOK_DATA


def rows(table: str) -> list[dict]:
    return yaml.safe_load((HANDBOOK_DATA / f"{table}.yaml").read_text(encoding="utf-8")) or []
