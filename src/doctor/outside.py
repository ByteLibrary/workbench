"""The base for data the doctor reads from outside: the handbook's tables, GitHub's API and other tools'
output. The doctor declares only the fields it uses, so the models ignore the rest; the handbook checks
its own tables against their JSON Schemas."""

from pydantic import BaseModel, ConfigDict


class Outside(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")
