"""The warehouse seam on Postgres, the Compose warehouse (AGENT_WAREHOUSE=postgres, the default).

The audit row is written as `agent_audit`, a role that may only insert into `ops.agent_queries`
(SL-10): `AUDIT_URL`, else dbt's own `DBT_*` host, port and database with the `agent_audit` login,
so the audit lands in the warehouse the query read. The readiness ledger is read with dbt's own
`DBT_*` connection variables and profiles.yml's defaults, as the read-only `agent_metrics` role in
the lab (SL-4). One connection per call, as the agent makes one audit row and one ledger read per
data call.
"""

from __future__ import annotations

import os
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from semantic_agent.warehouse import Readiness, WarehouseError, reason

AUDIT_SQL = """
insert into ops.agent_queries (
  agent, tool, user_id, session_id, invocation_id, call_id,
  metrics, filters, arguments, sql, rows_returned, freshness, error
) values (
  %(agent)s, %(tool)s, %(user_id)s, %(session_id)s, %(invocation_id)s, %(call_id)s,
  %(metrics)s, %(filters)s, %(arguments)s, %(sql)s, %(rows_returned)s, %(freshness)s, %(error)s
)
"""

READINESS_SQL = """
select p.product,
       (select max(r.interval_end) from ops.readiness r
         where r.product = p.product and r.status = 'ready') as ready_until,
       coalesce(own.max_age, pipeline.max_age) as max_age
from unnest(%(products)s::text[]) as p(product)
left join ops.product_deadlines own on own.product = p.product
left join ops.product_deadlines pipeline on pipeline.product = split_part(p.product, '.', 1)
order by p.product
"""


def audit_url() -> str:
    if url := os.environ.get("AUDIT_URL"):
        return url
    env = os.environ.get
    host, port = env("DBT_HOST", "warehouse"), env("DBT_PORT", "5432")
    return f"postgresql://agent_audit:agent_audit@{host}:{port}/{env('DBT_DBNAME', 'warehouse')}"


def read_url() -> str:
    env = os.environ.get
    user, password = env("DBT_USER", "warehouse"), env("DBT_PASSWORD", "warehouse")
    host, port = env("DBT_HOST", "warehouse"), env("DBT_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{env('DBT_DBNAME', 'warehouse')}"


def audit_params(row: dict[str, Any]) -> dict[str, Any]:
    """The audit row as the insert's parameters: the JSON columns wrapped for jsonb."""
    return {
        **row,
        "filters": Jsonb(row["filters"]) if row["filters"] is not None else None,
        "arguments": Jsonb(row["arguments"]),
    }


class PostgresWarehouse:
    def insert_audit(self, row: dict[str, Any]) -> None:
        try:
            with psycopg.connect(audit_url(), connect_timeout=10) as conn:
                conn.execute(AUDIT_SQL, audit_params(row))
        except psycopg.Error as e:
            raise WarehouseError(reason(e)) from e

    def readiness(
        self, products: list[str], *, agent: str | None = None, session_id: str | None = None
    ) -> list[Readiness]:
        try:
            with psycopg.connect(read_url(), connect_timeout=10) as conn:
                return conn.execute(READINESS_SQL, {"products": products}).fetchall()
        except psycopg.Error as e:
            raise WarehouseError(reason(e)) from e


def warehouse() -> PostgresWarehouse:
    return PostgresWarehouse()
