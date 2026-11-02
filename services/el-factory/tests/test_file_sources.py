"""Where the file sources (el_factory.tlc) are served: only on a warehouse that keeps their ledger,
and only where the build carries them with pyarrow (semantic/PLAN.md SL-19, issue #307)."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from el_factory.app import create_app
from tests.conftest import FakeFileLedger, FakeWarehouse, make_config

EXTRACT = {
    "source": "tlc",
    "entity": "yellow",
    "run_id": "manual__1",
    "interval_start": "2025-10-01T00:00:00+00:00",
    "interval_end": "2025-11-01T00:00:00+00:00",
}


@pytest.fixture
def warehouse() -> FakeWarehouse:
    return FakeWarehouse()  # no file ledger


def test_a_warehouse_without_a_file_ledger_serves_no_file_source(client):
    query = {"source": "tlc", "entity": "yellow", "month": "2025-10"}

    assert client.get("/publication", query_string=query).status_code == 404
    assert client.get("/months", query_string=query).status_code == 404
    assert client.post("/retire", json={**query, "keep": ["2025-10"]}).status_code == 404
    extract = client.post("/extract", json=EXTRACT)
    assert extract.status_code == 404
    assert extract.get_json()["error"] == "tlc is a file source this build does not serve"


def test_the_catalog_leaves_out_the_file_sources_it_does_not_serve(client):
    assert client.get("/catalog?pipeline=tlc").status_code == 404
    assert client.get("/catalog?pipeline=sales").status_code == 200


def test_a_warehouse_with_a_file_ledger_serves_them(storage):
    app = create_app(make_config(), storage, FakeFileLedger())
    client = app.test_client()

    response = client.get("/catalog?pipeline=tlc")
    assert response.status_code == 200
    assert response.get_json() == [
        {"source": "tlc", "entity": "yellow"},
        {"source": "tlc", "entity": "green"},
    ]
    assert client.get("/months?source=tlc&entity=yellow").get_json()["months"] == []


def run(code: str) -> list:
    env = {k: v for k, v in os.environ.items() if k != "ELF_WAREHOUSE"}
    out = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout)


def test_without_pyarrow_a_file_ledger_serves_no_file_source():
    """A build without the `files` extra still starts, with the paged sources only."""
    code = (
        "import json, sys\n"
        "sys.modules['pyarrow'] = None  # not installed\n"
        "from el_factory.app import create_app\n"
        "from tests.conftest import FakeFileLedger, FakeStorage, make_config\n"
        "client = create_app(make_config(), FakeStorage(), FakeFileLedger()).test_client()\n"
        "print(json.dumps([client.get('/catalog?pipeline=tlc').status_code,\n"
        "                  client.get('/catalog?pipeline=sales').status_code]))\n"
    )
    assert run(code) == [404, 200]


def test_the_app_imports_no_file_source_until_a_ledger_serves_them():
    code = (
        "import json, sys\n"
        "from el_factory.app import create_app\n"
        "from tests.conftest import FakeFileLedger, FakeStorage, FakeWarehouse, make_config\n"
        "seen = []\n"
        "for warehouse in (FakeWarehouse(), FakeFileLedger()):\n"
        "    create_app(make_config(), FakeStorage(), warehouse)\n"
        "    seen.append(['pyarrow' in sys.modules, 'el_factory.tlc' in sys.modules])\n"
        "print(json.dumps(seen))\n"
    )
    assert run(code) == [[False, False], [True, True]]
