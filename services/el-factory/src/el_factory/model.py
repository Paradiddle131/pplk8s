from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Interval:
    """Half-open UTC interval [start, end)."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class Page:
    rows: list[dict[str, Any]]
    next_cursor: int | None


@dataclass(frozen=True)
class Table:
    """A source-owned warehouse table; the warehouse layer appends the metadata columns."""

    name: str
    columns: tuple[tuple[str, str], ...]
