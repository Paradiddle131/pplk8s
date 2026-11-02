"""The warehouse seam: where audit rows go and the ledger is read (semantic/PLAN.md SL-19).

`audit.py` writes one row per data call to `ops.agent_queries` (SL-10) and `freshness.py` reads
`ops.readiness` and `ops.product_deadlines` (SL-4) through a `Warehouse`, never through a driver, so
an image carries only the driver of the warehouse it runs on: `AGENT_WAREHOUSE` picks the
implementation, `postgres` (the default: the lab's Compose warehouse, `warehouse_postgres.py`) or
`bigquery` (the lab project, `warehouse_bigquery.py`), and only the chosen module, with its driver,
is imported.

A warehouse that cannot be reached, refuses or is misconfigured raises `WarehouseError`, whatever
its driver says, so the callers fail the same way on either: the audit withholds the result and the
freshness says it is unknown.
"""

from __future__ import annotations

import datetime
from typing import Any, Protocol

from semantic_agent.seam import choose

# The implementation of each AGENT_WAREHOUSE value, imported only when chosen.
IMPLEMENTATIONS = {
    "postgres": "semantic_agent.warehouse_postgres",
    "bigquery": "semantic_agent.warehouse_bigquery",
}
# Each implementation's driver, as the extra of pyproject.toml that installs it.
EXTRAS = {"postgres": "postgres", "bigquery": "bigquery"}

# One product's ledger row: its newest ready interval end and its deadline (D37), either unknown.
Readiness = tuple[str, datetime.datetime | None, datetime.timedelta | None]


class WarehouseError(Exception):
    """The warehouse could not be reached, refused the statement, or is not configured."""


class Warehouse(Protocol):
    def insert_audit(self, row: dict[str, Any]) -> None:
        """Inserts one audit row (audit.audit_row's keys) into ops.agent_queries."""
        ...

    def readiness(
        self, products: list[str], *, agent: str | None = None, session_id: str | None = None
    ) -> list[Readiness]:
        """Each product's newest `ready` interval end and its deadline, its own or its
        pipeline's, ordered by product; `agent` and `session_id` name who asked, where the
        warehouse can record it (BigQuery's job labels)."""
        ...


def reason(error: BaseException) -> str:
    """The first line of an error, for a sentence the model or the audit is shown."""
    lines = str(error).strip().splitlines()
    return lines[0] if lines else type(error).__name__


def warehouse() -> Warehouse:
    """The warehouse AGENT_WAREHOUSE names (default `postgres`), its module imported when chosen."""
    module = choose(
        "AGENT_WAREHOUSE", IMPLEMENTATIONS, default="postgres", extras=EXTRAS, error=WarehouseError
    )
    return module.warehouse()
