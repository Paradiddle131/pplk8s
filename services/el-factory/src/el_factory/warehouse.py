"""Warehouse port and its Postgres adapter; ds_source tables follow the shared contract."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
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


# File-source chunks (D34) are keyed by the file version they came from, so a resumed or retried
# request replaces exactly one chunk and a republished file never mixes with the old one.
CHUNK_METADATA_COLUMNS = (
    ("_run_id", "text NOT NULL"),
    ("_source_uri", "text NOT NULL"),
    ("_etag", "text NOT NULL"),
    ("_chunk", "integer NOT NULL"),
    ("_loaded_at", "timestamptz NOT NULL DEFAULT now()"),
)


@dataclass(frozen=True)
class ChunkLoad:
    run_id: str
    source_uri: str
    etag: str
    chunk: int


@dataclass(frozen=True)
class FileProgress:
    loaded: frozenset[int]
    completed: bool


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
    def __init__(self, dsn: str, schema: str = SCHEMA) -> None:
        self._dsn = dsn
        self._schema = schema

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
        qualified = sql.Identifier(self._schema, table.name)
        columns = [*table.columns, *metadata]
        definition = sql.SQL(", ").join(
            sql.SQL("{} {}").format(sql.Identifier(name), sql.SQL(kind)) for name, kind in columns
        )
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [_lock_key(self._schema, table.name)],
            )
            cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(qualified, definition))
            cur.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} ({})").format(
                    sql.Identifier(f"{table.name}_load_key_idx"),
                    qualified,
                    sql.SQL(", ").join(sql.Identifier(c) for c in key),
                )
            )

    def replace_page(self, table: Table, load: PageLoad, rows: Sequence[Mapping[str, Any]]) -> int:
        qualified = sql.Identifier(self._schema, table.name)
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
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [_page_key(self._schema, table, load)],
            )
            cur.execute(delete, delete_params)
            cur.executemany(insert, params)
        return len(params)

    def replace_file(
        self, table: Table, load: FileLoad, rows: Sequence[Mapping[str, Any]]
    ) -> int | None:
        qualified = sql.Identifier(self._schema, table.name)
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
                [f"{_lock_key(self._schema, table.name)}|{load.source_uri}"],
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

    # ---- file-source chunks (D34) ------------------------------------------------------------

    def landing_columns(self, table_name: str) -> dict[str, str]:
        """Data columns of a chunk landing table (metadata columns left out); {} if absent."""
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT column_name, data_type FROM information_schema.columns"
                " WHERE table_schema = %s AND table_name = %s",
                [self._schema, table_name],
            )
            return {name: kind for name, kind in cur.fetchall() if not name.startswith("_")}

    def prepare_landing_table(
        self,
        table_name: str,
        add: Sequence[tuple[str, str]],
        widen: Sequence[tuple[str, str]],
    ) -> None:
        """Create the table if needed, add new columns, widen numeric ones; all under one lock."""
        qualified = sql.Identifier(self._schema, table_name)
        metadata = sql.SQL(", ").join(
            sql.SQL("{} {}").format(sql.Identifier(n), sql.SQL(k))
            for n, k in CHUNK_METADATA_COLUMNS
        )
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [_lock_key(self._schema, table_name)],
            )
            cur.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(qualified, metadata))
            cur.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (_source_uri, _etag, _chunk)").format(
                    sql.Identifier(f"{table_name}_chunk_idx"), qualified
                )
            )
            for name, kind in add:
                cur.execute(
                    sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} {}").format(
                        qualified, sql.Identifier(name), sql.SQL(kind)
                    )
                )
            if not widen:
                return
            # Postgres refuses to retype a column a view reads, so the views over the table (dbt's
            # bronze, and views on those) are dropped and recreated around the change, in this
            # transaction. BigQuery's views are late-binding and need none of this (#72).
            views = _dependent_views(cur, self._schema, table_name)
            for schema, name, _, _ in reversed(views):
                cur.execute(sql.SQL("DROP VIEW {}").format(sql.Identifier(schema, name)))
            for name, kind in widen:
                cur.execute(
                    sql.SQL("ALTER TABLE {} ALTER COLUMN {} TYPE {}").format(
                        qualified, sql.Identifier(name), sql.SQL(kind)
                    )
                )
            for schema, name, definition, columns in views:
                # Postgres stores a cast to a column's current type as a bare column, so the saved
                # definition would follow the widened type; casting back keeps each view's columns.
                select = sql.SQL(", ").join(
                    sql.SQL("cast({} AS {}) AS {}").format(
                        sql.Identifier(column), sql.SQL(kind), sql.Identifier(column)
                    )
                    for column, kind in columns
                )
                cur.execute(
                    sql.SQL("CREATE VIEW {} AS SELECT {} FROM ({}) AS widened").format(
                        sql.Identifier(schema, name), select, sql.SQL(definition.rstrip("; \n"))
                    )
                )

    def file_progress(self, source_uri: str, etag: str) -> FileProgress:
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT chunk FROM ops.file_chunks WHERE source_uri = %s AND etag = %s",
                [source_uri, etag],
            )
            loaded = frozenset(row[0] for row in cur.fetchall())
            cur.execute(
                "SELECT 1 FROM ops.file_versions WHERE source_uri = %s AND etag = %s",
                [source_uri, etag],
            )
            return FileProgress(loaded=loaded, completed=cur.fetchone() is not None)

    def replace_chunk(
        self, table_name: str, load: ChunkLoad, columns: Sequence[str], csv: Iterable[bytes]
    ) -> int:
        """Replace one chunk's rows from CSV (data columns then metadata) and record it."""
        qualified = sql.Identifier(self._schema, table_name)
        names = [*columns, "_run_id", "_source_uri", "_etag", "_chunk"]
        copy = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv)").format(
            qualified, sql.SQL(", ").join(sql.Identifier(n) for n in names)
        )
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [f"{_lock_key(self._schema, table_name)}|{load.source_uri}|{load.chunk}"],
            )
            cur.execute(
                sql.SQL(
                    "DELETE FROM {} WHERE _source_uri = %s AND _etag = %s AND _chunk = %s"
                ).format(qualified),
                [load.source_uri, load.etag, load.chunk],
            )
            with cur.copy(copy) as writer:
                for part in csv:
                    writer.write(part)
            rows = cur.rowcount
            cur.execute(
                "INSERT INTO ops.file_chunks (source_uri, etag, chunk, rows)"
                " VALUES (%s, %s, %s, %s)"
                " ON CONFLICT (source_uri, etag, chunk)"
                " DO UPDATE SET rows = EXCLUDED.rows, loaded_at = now()",
                [load.source_uri, load.etag, load.chunk, rows],
            )
        return rows

    def complete_version(self, table_name: str, source_uri: str, etag: str) -> None:
        """Mark a file version complete and drop every other version's rows and chunk records."""
        qualified = sql.Identifier(self._schema, table_name)
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [f"{_lock_key(self._schema, table_name)}|{source_uri}"],
            )
            cur.execute(
                "INSERT INTO ops.file_versions (source_uri, etag) VALUES (%s, %s)"
                " ON CONFLICT (source_uri, etag) DO NOTHING",
                [source_uri, etag],
            )
            cur.execute(
                sql.SQL("DELETE FROM {} WHERE _source_uri = %s AND _etag <> %s").format(qualified),
                [source_uri, etag],
            )
            cur.execute(
                "DELETE FROM ops.file_chunks WHERE source_uri = %s AND etag <> %s",
                [source_uri, etag],
            )

    def file_uris(self, pattern: str) -> list[str]:
        """Every file URI the chunk ledgers hold (loading or complete) matching a LIKE pattern."""
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT source_uri FROM ops.file_chunks WHERE source_uri LIKE %(p)s"
                " UNION SELECT source_uri FROM ops.file_versions WHERE source_uri LIKE %(p)s",
                {"p": pattern},
            )
            return sorted(row[0] for row in cur.fetchall())

    def retire_file(self, table_name: str, source_uri: str) -> int:
        """Delete every landed row of a file (all versions) and its ledger rows; return the rows.

        The freed space goes back to the table, not the disk: autovacuum reclaims it for the next
        month's load (D35). BigQuery drops the month's partition instead.
        """
        qualified = sql.Identifier(self._schema, table_name)
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                [f"{_lock_key(self._schema, table_name)}|{source_uri}"],
            )
            rows = 0
            cur.execute("SELECT to_regclass(%s)", [f'"{self._schema}"."{table_name}"'])
            row = cur.fetchone()
            if row is not None and row[0] is not None:
                cur.execute(
                    sql.SQL("DELETE FROM {} WHERE _source_uri = %s").format(qualified),
                    [source_uri],
                )
                rows = cur.rowcount
            cur.execute("DELETE FROM ops.file_chunks WHERE source_uri = %s", [source_uri])
            cur.execute("DELETE FROM ops.file_versions WHERE source_uri = %s", [source_uri])
        return rows


def _dependent_views(
    cur: psycopg.Cursor, schema: str, table_name: str
) -> list[tuple[str, str, str, list[tuple[str, str]]]]:
    """(schema, name, definition, [(column, type)]) of every view reading the table, directly or
    through other views, each listed after the views it reads, so they can be recreated in order
    and dropped in reverse."""
    cur.execute(
        """
        WITH RECURSIVE dependents(oid, depth) AS (
            SELECT rewrite.ev_class, 1
            FROM pg_depend dep
            JOIN pg_rewrite rewrite ON rewrite.oid = dep.objid
            WHERE dep.classid = 'pg_rewrite'::regclass
              AND dep.refobjid = format('%%I.%%I', %s::text, %s::text)::regclass
              AND rewrite.ev_class <> dep.refobjid
            UNION ALL
            SELECT rewrite.ev_class, dependents.depth + 1
            FROM dependents
            JOIN pg_depend dep
              ON dep.refobjid = dependents.oid AND dep.classid = 'pg_rewrite'::regclass
            JOIN pg_rewrite rewrite ON rewrite.oid = dep.objid
            WHERE rewrite.ev_class <> dependents.oid
        )
        SELECT ns.nspname, cls.relname, pg_get_viewdef(cls.oid),
            (SELECT array_agg(array[att.attname::text, format_type(att.atttypid, att.atttypmod)]
                              ORDER BY att.attnum)
             FROM pg_attribute att
             WHERE att.attrelid = cls.oid AND att.attnum > 0 AND NOT att.attisdropped)
        FROM (SELECT oid, max(depth) AS depth FROM dependents GROUP BY oid) found
        JOIN pg_class cls ON cls.oid = found.oid
        JOIN pg_namespace ns ON ns.oid = cls.relnamespace
        WHERE cls.relkind = 'v'
        ORDER BY found.depth, ns.nspname, cls.relname
        """,
        [schema, table_name],
    )
    return [(row[0], row[1], row[2], [(c, t) for c, t in row[3]]) for row in cur.fetchall()]


def _lock_key(schema: str, table_name: str) -> str:
    return f"{schema}.{table_name}"


def _page_key(schema: str, table: Table, load: PageLoad) -> str:
    return (
        f"{_lock_key(schema, table.name)}|{load.run_id}|{load.interval.start.isoformat()}"
        f"|{load.interval.end.isoformat()}|{load.page}"
    )
