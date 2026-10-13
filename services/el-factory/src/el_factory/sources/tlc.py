"""NYC TLC trip files: one Parquet file per trip type and data month (PLAN.md D34-D35).

EL Factory fetches the file itself, by HTTP byte range, one row group (a *chunk*) per step, and
lands every published column under its lower-cased name in ``ds_source.tlc_<entity>``.
The landing table evolves the way a BigQuery load job with ``ALLOW_FIELD_ADDITION`` and
``ALLOW_FIELD_RELAXATION`` would: new columns are added, integers widen to bigint and then to
double, and any other type change is refused.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet as pq

from el_factory.errors import ApiError, BadRequest
from el_factory.model import Interval

SOURCE = "tlc"
DEFAULT_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"

MONTH_PATTERN = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")

# Postgres types of landed columns, and the widening order among the numeric ones.
INTEGER, BIGINT, DOUBLE = "integer", "bigint", "double precision"
NUMERIC_RANK = {INTEGER: 0, BIGINT: 1, DOUBLE: 2}


class SchemaConflict(ApiError):
    """A column changed type in a way a load job refuses; reloading the same file cannot help."""

    def __init__(self, message: str) -> None:
        super().__init__(502, message, retryable=False)


@dataclass(frozen=True)
class TlcEntity:
    source: str
    name: str
    base_url: str

    @property
    def table_name(self) -> str:
        return f"tlc_{self.name}"

    def url(self, month: str) -> str:
        return f"{self.base_url.rstrip('/')}/{self.name}_tripdata_{month}.parquet"


def entities(base_url: str) -> list[TlcEntity]:
    # FHVHV stays registered for the big-file drill; the catalog keeps it disabled (D35).
    return [TlcEntity(SOURCE, name, base_url) for name in ("yellow", "green", "fhvhv")]


def data_month(interval: Interval) -> str:
    """The interval must be exactly one calendar month (UTC); return it as ``YYYY-MM``."""
    start, end = interval.start, interval.end
    following = datetime(start.year + start.month // 12, start.month % 12 + 1, 1, tzinfo=UTC)
    if start != datetime(start.year, start.month, 1, tzinfo=UTC) or end != following:
        raise BadRequest("a tlc interval must span exactly one calendar month (UTC)")
    return f"{start.year:04d}-{start.month:02d}"


def parse_month(raw: str | None) -> str:
    """A data month as ``YYYY-MM`` (a query parameter), or BadRequest."""
    if raw is None or not MONTH_PATTERN.fullmatch(raw):
        raise BadRequest("'month' is required and must be YYYY-MM")
    return raw


def postgres_type(name: str, kind: pa.DataType) -> str | None:
    """Landing type of an Arrow type; None for an all-null column (nothing to learn from it)."""
    if pa.types.is_null(kind):
        return None
    if pa.types.is_boolean(kind):
        return "boolean"
    if pa.types.is_integer(kind):
        return INTEGER if kind.bit_width < 32 or kind == pa.int32() else BIGINT
    if pa.types.is_floating(kind):
        return DOUBLE
    if pa.types.is_string(kind) or pa.types.is_large_string(kind):
        return "text"
    if pa.types.is_timestamp(kind):
        return "timestamp with time zone" if kind.tz else "timestamp without time zone"
    if pa.types.is_date(kind):
        return "date"
    raise SchemaConflict(f"column {name!r} has an unsupported type {kind}")


@dataclass(frozen=True)
class ColumnPlan:
    """What a chunk needs from the landing table before it loads."""

    columns: tuple[tuple[str, str], ...]  # (lower-cased name, type) of every typed file column
    add: tuple[tuple[str, str], ...]
    widen: tuple[tuple[str, str], ...]


def plan_columns(schema: pa.Schema, existing: dict[str, str]) -> ColumnPlan:
    """Compare a file's schema with the landing table's columns (lower-cased name -> type)."""
    columns: list[tuple[str, str]] = []
    add: list[tuple[str, str]] = []
    widen: list[tuple[str, str]] = []
    seen: set[str] = set()
    for field in schema:
        name = field.name.lower()
        if name in seen:
            raise SchemaConflict(f"columns {field.name!r} and another collide when lower-cased")
        seen.add(name)
        if name.startswith("_"):
            raise SchemaConflict(f"column {field.name!r} clashes with the metadata columns")
        incoming = postgres_type(field.name, field.type)
        if incoming is None:
            continue  # all-null: leave it out; a later file with a real type adds it
        columns.append((name, incoming))
        current = existing.get(name)
        if current is None:
            add.append((name, incoming))
        elif current == incoming:
            continue
        elif current in NUMERIC_RANK and incoming in NUMERIC_RANK:
            if NUMERIC_RANK[incoming] > NUMERIC_RANK[current]:
                widen.append((name, incoming))
        else:
            raise SchemaConflict(
                f"column {name!r} is {current} in the warehouse but {incoming} in the file"
            )
    return ColumnPlan(tuple(columns), tuple(add), tuple(widen))


def chunk_span(metadata: pq.FileMetaData, chunk: int) -> tuple[int, int]:
    """The byte range ``[start, end)`` that holds every column chunk of one row group."""
    group = metadata.row_group(chunk)
    starts, ends = [], []
    for index in range(group.num_columns):
        column = group.column(index)
        start = column.data_page_offset
        if column.has_dictionary_page and column.dictionary_page_offset is not None:
            start = min(start, column.dictionary_page_offset)
        starts.append(start)
        ends.append(start + column.total_compressed_size)
    return min(starts), max(ends)
