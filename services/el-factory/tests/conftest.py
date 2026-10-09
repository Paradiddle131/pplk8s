from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from el_factory.app import create_app
from el_factory.config import Config
from el_factory.model import Table
from el_factory.warehouse import PageLoad

REPO_CATALOG = Path(__file__).resolve().parents[1] / "catalog.yaml"


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload(self, uri: str, data: bytes) -> None:
        self.objects[uri] = data

    def download(self, uri: str) -> bytes:
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

    def row_count(self, table_name: str) -> int:
        return sum(len(rows) for rows in self.tables.get(table_name, {}).values())


def make_config(**overrides: Any) -> Config:
    values: dict[str, Any] = {
        "warehouse_dsn": "postgresql://unused",
        "storage_emulator_host": None,
        "gcs_bucket": "staging",
        "gcp_project": "pplk8s",
        "page_size": 100,
        "fail_rate": 0.0,
        "catalog_path": REPO_CATALOG,
        "open_meteo_url": "http://open-meteo.test/v1/archive",
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
    def build(**overrides: Any):
        app = create_app(make_config(**overrides), storage, warehouse)
        app.config["TESTING"] = True
        return app.test_client()

    return build


@pytest.fixture
def client(make_client):
    return make_client()
