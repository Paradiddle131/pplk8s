"""File entities: NDJSON files that land in object storage and are loaded by ``POST /load``.

Unlike the paged sources, a file entity is not fetched by EL Factory; a producer drops the file and
an object event names it.  Each row must carry exactly the entity's columns.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from el_factory.errors import InvalidFile, NotFound
from el_factory.model import Table

PARTNER_RETURNS_TABLE = Table(
    "partner_returns",
    (
        ("return_id", "text"),
        ("order_id", "text"),
        ("returned_at", "timestamptz"),
        ("amount", "numeric(12,2)"),
        ("reason", "text"),
    ),
)


@dataclass(frozen=True)
class FileEntity:
    name: str
    table: Table


def entities() -> list[FileEntity]:
    return [FileEntity("partner_returns", PARTNER_RETURNS_TABLE)]


class FileRegistry:
    def __init__(self, items: list[FileEntity]) -> None:
        self._items = {item.name: item for item in items}

    def entities(self) -> list[FileEntity]:
        return list(self._items.values())

    def get(self, name: str) -> FileEntity:
        found = self._items.get(name)
        if found is None:
            raise NotFound(f"unknown file entity: {name}")
        return found


def parse_ndjson(entity: FileEntity, data: bytes) -> list[dict[str, Any]]:
    """Parse and validate a landed NDJSON file; any bad line rejects the whole file."""
    expected = {name for name, _ in entity.table.columns}
    rows: list[dict[str, Any]] = []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidFile(f"{entity.name}: file is not UTF-8") from exc
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InvalidFile(f"{entity.name}: line {number} is not JSON") from exc
        if not isinstance(row, dict) or set(row) != expected:
            raise InvalidFile(
                f"{entity.name}: line {number} must have exactly the keys {sorted(expected)}"
            )
        rows.append(row)
    return rows
