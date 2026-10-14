"""Months a file source holds, and retiring the ones outside the caller's scope (D35, issue #87).

The caller (the DAG) owns the policy and sends the months to keep; EL Factory owns the mechanics:
the landed rows of every other month, every version, and their chunk-ledger rows are deleted, so a
later load of a retired month starts from scratch. BigQuery expires the month's partition instead.
"""

from __future__ import annotations

from typing import Any, Protocol

from el_factory.sources.tlc import TlcEntity


class RetentionWarehouse(Protocol):
    def file_uris(self, pattern: str) -> list[str]: ...

    def retire_file(self, table_name: str, source_uri: str) -> int: ...


def held_months(entity: TlcEntity, warehouse: RetentionWarehouse) -> list[str]:
    """Months with any ledger row (loading or complete) for this entity, oldest first."""
    months = {entity.month_of(uri) for uri in warehouse.file_uris(_pattern(entity))}
    return sorted(m for m in months if m is not None)


def retire(entity: TlcEntity, keep: list[str], warehouse: RetentionWarehouse) -> dict[str, Any]:
    """Retire every held month not in ``keep``; return the months retired and rows deleted."""
    retired: list[dict[str, Any]] = []
    for uri in warehouse.file_uris(_pattern(entity)):
        month = entity.month_of(uri)
        if month is None or month in keep:
            continue
        retired.append({"month": month, "rows": warehouse.retire_file(entity.table_name, uri)})
    return {
        "status": "ok",
        "source": entity.source,
        "entity": entity.name,
        "kept": sorted(keep),
        "retired": retired,
        "rows": sum(r["rows"] for r in retired),
    }


def _pattern(entity: TlcEntity) -> str:
    # A LIKE pattern over-matching the entity's URLs (`_` is a wildcard); month_of() is exact.
    return entity.url("%")
