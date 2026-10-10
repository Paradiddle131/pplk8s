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

# File entities (POST /load) are keyed by the object they came from, not by run and interval.
FILE_METADATA_COLUMNS = (
    ("_run_id", "text NOT NULL"),
    ("_source_uri", "text NOT NULL"),
    ("_generation", "bigint NOT NULL"),
    ("_loaded_at", "timestamptz NOT NULL DEFAULT now()"),
)


@dataclass(frozen=True)
class FileLoad:
    run_id: str
    source_uri: str
    generation: int


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

    def ensure_file_table(self, table: Table) -> None: ...

    def replace_file(
        self, table: Table, load: FileLoad, rows: Sequence[Mapping[str, Any]]
    ) -> int | None:
        """Replace every row of the object with this generation's rows; return rows written.

        Returns None, writing nothing, when a newer generation of the object is already loaded.
        """
        ...


class PostgresWarehouse:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def ensure_table(self, table: Table) -> None:
        self._ensure(
            table, METADATA_COLUMNS, ("_run_id", "_interval_start", "_interval_end", "_page")
        )

    def ensure_file_table(self, table: Table) -> None:
        self._ensure(table, FILE_METADATA_COLUMNS, ("_source_uri", "_generation"))

    def _ensure(
        self, table: Table, metadata: Sequence[tuple[str, str]], key: Sequence[str]
    ) -> None:
        # The advisory lock serialises concurrent gunicorn workers creating the same table.
        qualified = sql.Identifier(SCHEMA, table.name)
        columns = [*table.columns, *metadata]
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
                    sql.SQL(", ").join(sql.Identifier(c) for c in key),
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

    def replace_file(
        self, table: Table, load: FileLoad, rows: Sequence[Mapping[str, Any]]
    ) -> int | None:
        qualified = sql.Identifier(SCHEMA, table.name)
        names = [name for name, _ in table.columns]
        meta = ["_run_id", "_source_uri", "_generation"]
        insert = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            qualified,
            sql.SQL(", ").join(sql.Identifier(n) for n in [*names, *meta]),
            sql.SQL(", ").join(sql.Placeholder() for _ in [*names, *meta]),
        )
        params = [
            [row[name] for name in names] + [load.run_id, load.source_uri, load.generation]
            for row in rows
        ]
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            # One lock per object, so loads of two generations never interleave.
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [f"{_lock_key(table)}|{load.source_uri}"],
            )
            cur.execute(
                sql.SQL("SELECT max(_generation) FROM {} WHERE _source_uri = %s").format(qualified),
                [load.source_uri],
            )
            row = cur.fetchone()
            if row is not None and row[0] is not None and row[0] > load.generation:
                return None
            cur.execute(
                sql.SQL("DELETE FROM {} WHERE _source_uri = %s").format(qualified),
                [load.source_uri],
            )
            cur.executemany(insert, params)
        return len(params)


def _lock_key(table: Table) -> str:
    return f"{SCHEMA}.{table.name}"


def _page_key(table: Table, load: PageLoad) -> str:
    return (
        f"{_lock_key(table)}|{load.run_id}|{load.interval.start.isoformat()}"
        f"|{load.interval.end.isoformat()}|{load.page}"
    )
