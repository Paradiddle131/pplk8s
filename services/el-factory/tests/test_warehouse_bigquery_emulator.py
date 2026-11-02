"""The BigQuery warehouse against the BigQuery emulator (Compose profile `bigquery`, the one
`make bigquery-emulator-check` starts): real load jobs and transactions, so a reload replaces rows
instead of adding them, as on Postgres.

Tables land in a throwaway dataset, so the emulator's own datasets are never touched. Without an
emulator at TEST_BQ_API_ENDPOINT (default the Compose one) the tests skip, unless
PPLK8S_REQUIRE_BIGQUERY=1.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest
import requests

from el_factory.model import Interval, Table
from el_factory.warehouse import FileLoad, PageLoad
from el_factory.warehouse_bigquery import BigQueryWarehouse, client

ENDPOINT = os.environ.get("TEST_BQ_API_ENDPOINT", "http://localhost:9050")
PROJECT = "pplk8s-lab"  # the emulator's (platform/compose/compose.yaml)
TABLE = Table("orders", (("order_id", "text"), ("amount", "numeric(12,2)")))
DAY = Interval(datetime(2025, 10, 1, tzinfo=UTC), datetime(2025, 10, 2, tzinfo=UTC))


@pytest.fixture
def emulator():
    try:
        requests.get(f"{ENDPOINT}/bigquery/v2/projects/{PROJECT}/datasets", timeout=3)
    except requests.RequestException as exc:
        message = f"no BigQuery emulator at {ENDPOINT} (docker compose --profile bigquery): {exc}"
        if os.environ.get("PPLK8S_REQUIRE_BIGQUERY") == "1":
            pytest.fail(message)
        pytest.skip(message)
    bq = client(PROJECT, ENDPOINT, "")
    dataset = f"test_elf_{uuid.uuid4().hex[:8]}"
    bq.create_dataset(f"{PROJECT}.{dataset}")
    yield bq, dataset, BigQueryWarehouse(lambda: bq, dataset=dataset, maximum_bytes_billed=2**30)
    bq.delete_dataset(f"{PROJECT}.{dataset}", delete_contents=True, not_found_ok=True)


def landed(bq, dataset: str, columns: str) -> list[tuple]:
    sql = f"select {columns} from `{PROJECT}.{dataset}.orders` order by {columns}"
    return [tuple(row) for row in bq.query(sql).result()]


def tables(bq, dataset: str) -> list[str]:
    return sorted(t.table_id for t in bq.list_tables(f"{PROJECT}.{dataset}"))


ROWS = [{"order_id": "a", "amount": "1.50"}, {"order_id": "b", "amount": 2}]


def test_a_first_page_replaces_its_runs_interval(emulator):
    bq, dataset, store = emulator
    store.ensure_table(TABLE)
    store.ensure_table(TABLE)  # a second ensure leaves it as it is

    assert store.replace_page(TABLE, PageLoad("r1", DAY, 0, "gs://s/p0"), ROWS) == 2
    store.replace_page(TABLE, PageLoad("r1", DAY, 0, "gs://s/p0"), ROWS)  # a retry
    store.replace_page(TABLE, PageLoad("r2", DAY, 0, "gs://s/q0"), [ROWS[1]])  # another run

    assert landed(bq, dataset, "_run_id, _page, order_id") == [
        ("r1", 0, "a"),
        ("r1", 0, "b"),
        ("r2", 0, "b"),
    ]
    assert all(row[0] is not None for row in landed(bq, dataset, "_loaded_at"))

    store.replace_page(TABLE, PageLoad("r1", DAY, 0, "gs://s/p0"), [])  # the interval emptied

    assert landed(bq, dataset, "_run_id, _page, order_id") == [("r2", 0, "b")]
    assert tables(bq, dataset) == ["orders"]  # no staging table is left behind


@pytest.mark.xfail(
    strict=True,
    reason="emulator 0.8.1: in a script, the second statement's INT64 parameter after two"
    " TIMESTAMP ones binds wrong, so a later page's copy matches no staged row (real BigQuery"
    " binds it; the fake-client tests hold the SQL)",
)
def test_a_later_page_replaces_only_itself(emulator):
    bq, dataset, store = emulator
    store.ensure_table(TABLE)
    store.replace_page(TABLE, PageLoad("r1", DAY, 0, "gs://s/p0"), ROWS)

    store.replace_page(TABLE, PageLoad("r1", DAY, 1, "gs://s/p1"), [ROWS[0]])
    store.replace_page(TABLE, PageLoad("r1", DAY, 1, "gs://s/p1"), [ROWS[0]])  # a retry

    assert landed(bq, dataset, "_page, order_id") == [(0, "a"), (0, "b"), (1, "a")]


def test_files_replace_their_object_unless_superseded(emulator):
    bq, dataset, store = emulator
    store.ensure_file_table(TABLE)
    uri = "gs://landing/returns.ndjson"
    first = [{"order_id": "a", "amount": 1}, {"order_id": "b", "amount": 2}]

    assert store.replace_file(TABLE, FileLoad("r1", uri, 5), first) == 2
    assert store.replace_file(TABLE, FileLoad("r1", uri, 5), first) == 2  # a reload
    assert store.replace_file(TABLE, FileLoad("r2", uri, 4), [first[0]]) is None  # older
    assert landed(bq, dataset, "_generation, order_id") == [(5, "a"), (5, "b")]

    assert store.replace_file(TABLE, FileLoad("r3", uri, 6), [first[1]]) == 1

    assert landed(bq, dataset, "_generation, _run_id, order_id") == [(6, "r3", "b")]
    assert tables(bq, dataset) == ["orders"]
