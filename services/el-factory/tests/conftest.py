from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from el_factory.app import create_app
from el_factory.config import Config
from el_factory.model import Table
from el_factory.warehouse import FileLoad, PageLoad

REPO_CATALOG = Path(__file__).resolve().parents[1] / "catalog.yaml"


class FakeStorage:
    """In-memory bucket without versioning: only the live generation of an object is readable."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.generations: dict[str, int] = {}
        self._clock = 1_700_000_000_000_000

    def upload(self, uri: str, data: bytes) -> int:
        self._clock += 1
        self.objects[uri] = data
        self.generations[uri] = self._clock
        return self._clock

    def download(self, uri: str) -> bytes:
        return self.objects[uri]

    def download_generation(self, uri: str, generation: int) -> bytes | None:
        if self.generations.get(uri) != generation:
            return None
        return self.objects[uri]


@dataclass
class FakeWarehouse:
    """Keeps rows per table and mirrors the Postgres adapter's replace-by-page semantics."""

    tables: dict[str, dict[tuple[Any, ...], list[dict[str, Any]]]] = field(default_factory=dict)
    ensured: list[str] = field(default_factory=list)

    def ensure_table(self, table: Table) -> None:
        self.ensured.append(table.name)
        self.tables.setdefault(table.name, {})

    def replace_page(self, table: Table, load: PageLoad, rows: Sequence[Mapping[str, Any]]) -> int:
        key = (load.run_id, load.interval.start, load.interval.end, load.page)
        stored = [
            {
                **{name: row[name] for name, _ in table.columns},
                "_run_id": load.run_id,
                "_interval_start": load.interval.start,
                "_interval_end": load.interval.end,
                "_page": load.page,
                "_source_uri": load.source_uri,
            }
            for row in rows
        ]
        pages = self.tables.setdefault(table.name, {})
        if load.page == 0:
            for stale in [k for k in pages if k[:3] == key[:3]]:
                del pages[stale]
        pages[key] = stored
        return len(stored)

    def ensure_file_table(self, table: Table) -> None:
        self.ensure_table(table)

    def replace_file(
        self, table: Table, load: FileLoad, rows: Sequence[Mapping[str, Any]]
    ) -> int | None:
        objects = self.tables.setdefault(table.name, {})
        current = objects.get((load.source_uri,))
        if current and current[0]["_generation"] > load.generation:
            return None
        objects[(load.source_uri,)] = [
            {
                **{name: row[name] for name, _ in table.columns},
                "_run_id": load.run_id,
                "_source_uri": load.source_uri,
                "_generation": load.generation,
            }
            for row in rows
        ]
        return len(rows)

    def row_count(self, table_name: str) -> int:
        return sum(len(rows) for rows in self.tables.get(table_name, {}).values())


class FakeFileLedger(FakeWarehouse):
    """A warehouse that keeps a file ledger (el_factory.warehouse.FileLedger), so the app serves
    the file sources; the chunk and retention calls run on Postgres (test_tlc_extract)."""

    def landing_columns(self, table_name: str) -> dict[str, str]:
        raise NotImplementedError

    def prepare_landing_table(self, table_name: str, add: Any, widen: Any) -> None:
        raise NotImplementedError

    def file_progress(self, source_uri: str, etag: str) -> Any:
        raise NotImplementedError

    def replace_chunk(self, table_name: str, load: Any, columns: Any, csv: Any) -> int:
        raise NotImplementedError

    def complete_version(self, table_name: str, source_uri: str, etag: str) -> None:
        raise NotImplementedError

    def file_uris(self, pattern: str) -> list[str]:
        return []

    def retire_file(self, table_name: str, source_uri: str) -> int:
        raise NotImplementedError


def make_config(**overrides: Any) -> Config:
    values: dict[str, Any] = {
        "warehouse_dsn": "postgresql://unused",
        "storage_emulator_host": None,
        "gcs_bucket": "staging",
        "gcp_project": "pplk8s",
        "page_size": 100,
        "fail_rate": 0.0,
        # One page per request, so a test sees each page; budget tests set their own.
        "max_run_time": 0.0,
        "catalog_path": REPO_CATALOG,
        "open_meteo_url": "http://open-meteo.test/v1/archive",
        "tlc_base_url": "http://tlc.test/trip-data",
        "port": 8080,
    }
    values.update(overrides)
    return Config(**values)


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def warehouse() -> FakeWarehouse:
    return FakeWarehouse()


@pytest.fixture
def make_client(storage: FakeStorage, warehouse: FakeWarehouse):
    def build(clock: Callable[[], float] = time.monotonic, **overrides: Any):
        app = create_app(make_config(**overrides), storage, warehouse, clock=clock)
        app.config["TESTING"] = True
        return app.test_client()

    return build


@pytest.fixture
def client(make_client):
    return make_client()
