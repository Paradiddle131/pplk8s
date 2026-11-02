"""The readiness ledger on BigQuery against the Compose warehouse's (#209).

On Postgres `platform/compose/warehouse-init/01-schemas.sql` creates `ops.readiness` and
`ops.product_deadlines` and upserts the deadlines; on BigQuery `dbt/macros/agent_warehouse.sql`
does, so the agent's freshness reads the same columns and deadlines in both warehouses.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
INIT = (REPO / "platform" / "compose" / "warehouse-init" / "01-schemas.sql").read_text()
MACRO = (REPO / "dbt" / "macros" / "agent_warehouse.sql").read_text()
BIGQUERY = MACRO[MACRO.index("macro bigquery__agent_warehouse") :]


def columns(sql: str, table: str) -> list[str]:
    """The columns of `create table ... ops.<table> (...)`, plus Postgres' added ones, in order."""
    body = re.search(rf"ops\.{table} \((.*?)\n\)", sql, re.DOTALL)
    assert body, f"no create table for ops.{table}"
    names = [
        line.split()[0]
        for line in body.group(1).splitlines()
        if line.strip() and not line.strip().upper().startswith("PRIMARY KEY")
    ]
    added = re.findall(rf"ALTER TABLE ops\.{table} ADD COLUMN IF NOT EXISTS (\w+)", sql)
    return names + added


def test_bigquery_creates_the_ledger_with_the_compose_warehouses_columns() -> None:
    for table in ("readiness", "product_deadlines"):
        assert columns(BIGQUERY, table) == columns(INIT, table), table


def test_bigquery_holds_the_compose_warehouses_deadlines() -> None:
    init = {
        product: int(hours)
        for product, hours in re.findall(r"\('([a-z_.]+)', '(\d+) hours'\)", INIT)
    }
    macro = {
        product: int(hours)
        for product, hours in re.findall(r'\("([a-z_.]+)", (\d+)\)', BIGQUERY)
    }
    assert init and macro == init
