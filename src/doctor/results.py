"""What a check found."""

from dataclasses import dataclass, field


@dataclass
class Result:
    section: str
    name: str
    # True passed, False failed, None information only.
    ok: bool | None
    fix: str = ""
    # The repair --fix makes for this failure, if it is safe to make.
    repair: str | None = None
    details: list[str] = field(default_factory=list)
