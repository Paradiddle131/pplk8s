from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from el_factory.model import Interval, Page, Table

Fetch = Callable[[Interval, int], Page]


@dataclass(frozen=True)
class Entity:
    source: str
    name: str
    table: Table
    fetch: Fetch
