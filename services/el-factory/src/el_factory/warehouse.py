"""Warehouse port and its Postgres adapter; ds_source tables follow the shared contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import psycopg
from psycopg import sql

from el_factory.model import Interval, Table

SCHEMA = "ds_source"
METADATA_COLUMNS = (
    ("_run_id", "text NOT NULL"),
    ("_interval_start", "timestamptz NOT NULL"),
    ("_interval_end", "timestamptz NOT NULL"),
    ("_page", "integer NOT NULL"),
    ("_source_uri", "text NOT NULL"),
    ("_loaded_at", "timestamptz NOT NULL DEFAULT now()"),
)


@dataclass(frozen=True)
class PageLoad:
    run_id: str
    interval: Interval
    page: int
    source_uri: str


class Warehouse(Protocol):
    def ensure_table(self, table: Table) -> None: ...

    def replace_page(self, table: Table, load: PageLoad, rows: Sequence[Mapping[str, Any]]) -> int:
        """Replace one page atomically (page 0 clears the run+interval); return rows written."""
        ...


class PostgresWarehouse:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def ensure_table(self, table: Table) -> None:
        # The advisory lock serialises concurrent gunicorn workers creating the same table.
        qualified = sql.Identifier(SCHEMA, table.name)
        columns = [*table.columns, *METADATA_COLUMNS]
        definition = sql.SQL(", ").join(
            sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL(kind)) for name, kind in columns
        )
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [_lock_key(table)])
            cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(qualified, definition))
            cur.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} ({})").format(
                    sql.Identifier(f"{table.name}_load_key_idx"),
                    qualified,
                    sql.SQL(", ").join(
                        sql.Identifier(c)
                        for c in ("_run_id", "_interval_start", "_interval_end", "_page")
                    ),
                )
            )

    def replace_page(self, table: Table, load: PageLoad, rows: Sequence[Mapping[str, Any]]) -> int:
        qualified = sql.Identifier(SCHEMA, table.name)
        names = [name for name, _ in table.columns]
        meta = ["_run_id", "_interval_start", "_interval_end", "_page", "_source_uri"]
        insert = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            qualified,
            sql.SQL(", ").join(sql.Identifier(n) for n in [*names, *meta]),
            sql.SQL(", ").join(sql.Placeholder() for _ in [*names, *meta]),
        )
        # Page 0 starts a (re)load of the whole (run, interval): clearing every page keeps the
        # load idempotent per (entity, interval, run_id) even if a re-run yields fewer pages.
        scope = "" if load.page == 0 else " AND _page = %s"
        delete = sql.SQL(
            "DELETE FROM {} WHERE _run_id = %s AND _interval_start = %s AND _interval_end = %s"
            + scope
        ).format(qualified)
        delete_params: list[Any] = [load.run_id, load.interval.start, load.interval.end]
        if load.page:
            delete_params.append(load.page)
        params = [
            [row[name] for name in names]
            + [
                load.run_id,
                load.interval.start,
                load.interval.end,
                load.page,
                load.source_uri,
            ]
            for row in rows
        ]
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", [_page_key(table, load)]
            )
            cur.execute(delete, delete_params)
            cur.executemany(insert, params)
        return len(params)


def _lock_key(table: Table) -> str:
    return f"{SCHEMA}.{table.name}"


def _page_key(table: Table, load: PageLoad) -> str:
    return (
        f"{_lock_key(table)}|{load.run_id}|{load.interval.start.isoformat()}"
        f"|{load.interval.end.isoformat()}|{load.page}"
    )
