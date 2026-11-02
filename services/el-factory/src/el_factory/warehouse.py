"""The warehouse seam: where EL Factory's loads land (semantic/PLAN.md SL-19).

The app reaches the warehouse through a `Warehouse`, never through a driver, so an image carries
only the driver of the warehouse it runs on: `ELF_WAREHOUSE` picks the implementation (`postgres`,
the default: the lab's Compose warehouse, `warehouse_postgres.py`), and only the chosen module, with
its driver, is imported.
The file sources (`el_factory.tlc`: the chunked file extract and retention, PLAN.md D34-D35) need
more than a `Warehouse`: a `FileLedger`, which only Postgres keeps, so they are served only on it.

A warehouse that cannot be reached or refuses a statement raises `WarehouseError`, whatever its
driver says; `transient` tells the app whether the caller's retry is the remedy (a 503) or not.
ds_source tables follow the shared contract: each implementation adds the same metadata columns.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from el_factory.model import Interval, Table

if TYPE_CHECKING:
    from el_factory.config import Config

# The implementation of each ELF_WAREHOUSE value, imported only when chosen.
IMPLEMENTATIONS = {"postgres": "el_factory.warehouse_postgres"}
# Each implementation's driver, as the extra of pyproject.toml that installs it.
EXTRAS = {"postgres": "postgres"}


class WarehouseError(Exception):
    """The warehouse could not be reached or refused the statement.

    `transient` is true where a retry can succeed (a dropped or refused connection), so the app
    answers a retryable 503; anything else is the app's bug or the warehouse's state, a 500.
    """

    def __init__(self, message: str, *, transient: bool) -> None:
        super().__init__(message)
        self.transient = transient


@dataclass(frozen=True)
class PageLoad:
    run_id: str
    interval: Interval
    page: int
    source_uri: str


@dataclass(frozen=True)
class FileLoad:
    run_id: str
    source_uri: str
    generation: int


# File-source chunks (D34) are keyed by the file version they came from, so a resumed or retried
# request replaces exactly one chunk and a republished file never mixes with the old one.
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


@runtime_checkable
class FileLedger(Protocol):
    """What the file sources need besides a `Warehouse` (D34-D35): landing tables that take their
    columns from the files, chunks replaced one at a time, and the ledger of chunks and versions
    (`ops.file_chunks`, `ops.file_versions`) that resumes and retires them.

    Only Postgres implements it: the TLC months stay in the lab (semantic/PLAN.md SL-19), so the
    app serves file sources only on a warehouse that is a `FileLedger`.
    """

    def landing_columns(self, table_name: str) -> dict[str, str]:
        """Data columns of a chunk landing table (lower-cased name to type); {} if absent."""
        ...

    def prepare_landing_table(
        self,
        table_name: str,
        add: Sequence[tuple[str, str]],
        widen: Sequence[tuple[str, str]],
    ) -> None:
        """Create the table if needed, add new columns and widen numeric ones."""
        ...

    def file_progress(self, source_uri: str, etag: str) -> FileProgress: ...

    def replace_chunk(
        self, table_name: str, load: ChunkLoad, columns: Sequence[str], csv: Iterable[bytes]
    ) -> int:
        """Replace one chunk's rows from CSV (data columns, then metadata) and record it."""
        ...

    def complete_version(self, table_name: str, source_uri: str, etag: str) -> None:
        """Mark a file version complete and drop every other version's rows and chunk records."""
        ...

    def file_uris(self, pattern: str) -> list[str]:
        """Every file URI the ledger holds (loading or complete) matching a LIKE pattern."""
        ...

    def retire_file(self, table_name: str, source_uri: str) -> int:
        """Delete every landed row of a file (all versions) and its ledger rows; return the rows."""
        ...


def warehouse(config: Config) -> Warehouse:
    """The warehouse `config.warehouse` names (ELF_WAREHOUSE), its module imported when chosen."""
    name = config.warehouse
    try:
        module = importlib.import_module(IMPLEMENTATIONS[name])
    except ImportError as e:
        raise WarehouseError(
            f"the {name} warehouse needs the {EXTRAS[name]!r} extra of el-factory ({e})",
            transient=False,
        ) from e
    return module.from_config(config)
