"""The handbook's data tables, which several checks compare the machine and GitHub with."""

import yaml
from pydantic import BaseModel

from doctor.outside import Outside
from doctor.settings import HANDBOOK_DATA


class Code(Outside):
    """A row of a table identified by its code: repository kinds, contexts."""

    code: str


class HandbookRepository(Outside):
    name: str
    status: str
    visibility: str
    kind: str
    description: str
    context: str | None = None
    port_block: int | None = None


class PortRange(Outside):
    code: str
    first: int
    last: int


def rows[Row: BaseModel](table: str, model: type[Row]) -> list[Row]:
    data = yaml.safe_load((HANDBOOK_DATA / f"{table}.yaml").read_text(encoding="utf-8")) or []
    return [model.model_validate(row) for row in data]
