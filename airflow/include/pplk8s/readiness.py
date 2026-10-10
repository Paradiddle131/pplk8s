"""Readiness ledger, file-load ledger, and post-extraction checks on the warehouse (PLAN.md §3, D8).

All helpers talk to the warehouse stand-in over the ``warehouse`` Airflow connection, never
to Airflow's metadata DB (PLAN.md D12).  The ledger is ``ops.readiness`` with the primary key
``(product, interval_start, interval_end)``; writes are UPSERTs, so repeating a task or a whole
run rewrites the same row instead of adding one.

``ops.file_loads`` (PLAN.md D18) records every landed object generation a file-arrival DAG loaded,
keyed by ``(bucket, object, generation)``; it is the durable half of event dedupe.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk.exceptions import AirflowFailException

DEFAULT_CONN_ID = "warehouse"

# Event-time column of the entities that have one; its max is the watermark of an interval.
WATERMARK_COLUMNS = {
    "synthetic_orders": "order_ts",
    "open_meteo_hourly_weather": "observed_at",
}

UPSERT_SQL = """
INSERT INTO ops.readiness
    (product, interval_start, interval_end, watermark, run_id, status, updated_at)
VALUES (%(product)s, %(interval_start)s, %(interval_end)s, %(watermark)s,
        %(run_id)s, %(status)s, now())
ON CONFLICT (product, interval_start, interval_end) DO UPDATE SET
    watermark = EXCLUDED.watermark,
    run_id = EXCLUDED.run_id,
    status = EXCLUDED.status,
    updated_at = now()
"""

FILE_LOAD_SQL = """
INSERT INTO ops.file_loads (bucket, object, generation, entity, run_id, rows, loaded_at)
VALUES (%(bucket)s, %(object)s, %(generation)s, %(entity)s, %(run_id)s, %(rows)s, now())
ON CONFLICT (bucket, object, generation) DO UPDATE SET
    entity = EXCLUDED.entity,
    run_id = EXCLUDED.run_id,
    rows = EXCLUDED.rows,
    loaded_at = now()
"""

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _hook(conn_id: str) -> PostgresHook:
    return PostgresHook(postgres_conn_id=conn_id)


def record_readiness(
    product: str,
    interval_start: str | datetime,
    interval_end: str | datetime,
    watermark: str | datetime | None,
    run_id: str,
    status: str,
    *,
    conn_id: str = DEFAULT_CONN_ID,
) -> None:
    """Upsert one ``ops.readiness`` row (idempotent per product and interval)."""
    _hook(conn_id).run(
        UPSERT_SQL,
        parameters={
            "product": product,
            "interval_start": interval_start,
            "interval_end": interval_end,
            "watermark": watermark,
            "run_id": run_id,
            "status": status,
        },
    )


def readiness_state(
    product: str,
    interval_start: str | datetime,
    interval_end: str | datetime,
    *,
    conn_id: str = DEFAULT_CONN_ID,
) -> dict[str, Any] | None:
    """Return ``{status, watermark, run_id}`` of one ledger row, or None if it does not exist."""
    found = _hook(conn_id).get_first(
        "SELECT status, watermark, run_id FROM ops.readiness "
        "WHERE product = %(product)s AND interval_start = %(start)s AND interval_end = %(end)s",
        parameters={"product": product, "start": interval_start, "end": interval_end},
    )
    if not found:
        return None
    status, watermark, run_id = found
    return {
        "status": status,
        "watermark": watermark.isoformat() if watermark else None,
        "run_id": run_id,
    }


def file_already_loaded(
    bucket: str, name: str, generation: str | int, *, conn_id: str = DEFAULT_CONN_ID
) -> str | None:
    """Return the run_id that already loaded this object generation, or None."""
    found = _hook(conn_id).get_first(
        "SELECT run_id FROM ops.file_loads "
        "WHERE bucket = %(bucket)s AND object = %(object)s AND generation = %(generation)s",
        parameters={"bucket": bucket, "object": name, "generation": int(generation)},
    )
    return found[0] if found else None


def record_file_load(
    bucket: str,
    name: str,
    generation: str | int,
    entity: str,
    run_id: str,
    rows: int,
    *,
    conn_id: str = DEFAULT_CONN_ID,
) -> None:
    """Upsert one ``ops.file_loads`` row (idempotent per object generation)."""
    _hook(conn_id).run(
        FILE_LOAD_SQL,
        parameters={
            "bucket": bucket,
            "object": name,
            "generation": int(generation),
            "entity": entity,
            "run_id": run_id,
            "rows": rows,
        },
    )


def table_for(source: str, entity: str) -> str:
    """Name of the ``ds_source`` table EL Factory loads ``source.entity`` into."""
    table = f"{source}_{entity}"
    if not _IDENT.match(table):
        raise AirflowFailException(f"unsafe table name derived from {source!r}/{entity!r}")
    return table


def check_extraction(
    summaries: Iterable[dict[str, Any]],
    run_id: str,
    interval_start: str | datetime,
    interval_end: str | datetime,
    *,
    conn_id: str = DEFAULT_CONN_ID,
) -> dict[str, Any]:
    """Verify that each extracted entity landed in ``ds_source`` and compute the watermark.

    For every summary the number of ``ds_source`` rows tagged with this ``run_id`` and interval
    must equal the rows EL Factory reported (a mismatch means a partial or foreign load, which
    retrying the check cannot fix, so it fails fast).  The watermark is the latest event time
    loaded for the interval across entities that have one, or ``None``.
    """
    summaries = list(summaries)
    if not summaries:
        raise AirflowFailException("no extraction summaries to check")
    hook = _hook(conn_id)
    params = {"run_id": run_id, "start": interval_start, "end": interval_end}
    watermark: datetime | None = None
    counts: dict[str, int] = {}
    for summary in summaries:
        table = table_for(summary["source"], summary["entity"])
        column = WATERMARK_COLUMNS.get(table)
        select = f"count(*), max({column})" if column else "count(*), NULL"
        found, latest = hook.get_first(
            f"SELECT {select} FROM ds_source.{table} "  # noqa: S608 - identifiers are validated
            "WHERE _run_id = %(run_id)s AND _interval_start = %(start)s "
            "AND _interval_end = %(end)s",
            parameters=params,
        )
        if found != summary["rows"]:
            raise AirflowFailException(
                f"ds_source.{table} holds {found} rows for run {run_id}, "
                f"EL Factory reported {summary['rows']}"
            )
        counts[table] = found
        if latest is not None and (watermark is None or latest > watermark):
            watermark = latest
    return {
        "watermark": watermark.isoformat() if watermark else None,
        "rows": counts,
    }
