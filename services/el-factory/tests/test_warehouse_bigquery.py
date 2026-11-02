"""The warehouse seam on BigQuery (el_factory/warehouse_bigquery.py, #227) with a fake client: rows
go in by load jobs into a staging table, one transaction replaces the load's scope, every job is
labelled and every query capped, and the client's errors leave as WarehouseError."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
import requests
from google.api_core import exceptions as api_exceptions
from google.cloud import bigquery

from el_factory import warehouse_bigquery
from el_factory.config import Config, ConfigError
from el_factory.model import Interval, Table
from el_factory.warehouse import FileLedger, FileLoad, PageLoad, WarehouseError, warehouse
from el_factory.warehouse_bigquery import BigQueryWarehouse

TABLE = Table("synthetic_orders", (("order_id", "text"), ("amount", "numeric(12,2)")))
DAY = Interval(datetime(2025, 10, 1, tzinfo=UTC), datetime(2025, 10, 2, tzinfo=UTC))
CAP = 1073741824


class Job:
    def __init__(self, rows: list[Any] | None = None, error: Exception | None = None) -> None:
        self.rows = rows or []
        self.error = error

    def result(self, **_: Any) -> list[Any]:
        if self.error:
            raise self.error
        return self.rows


class FakeClient:
    """Records what the warehouse asks BigQuery for. It has no `insert_rows` or `insert_rows_json`,
    so a streaming insert (no free tier) would fail the test with an AttributeError."""

    project = "lab-project"

    def __init__(self, existing: set[str] = frozenset(), newer: bool = False) -> None:
        self.tables: dict[str, Any] = {name: None for name in existing}
        self.created: list[bigquery.Table] = []
        self.deleted: list[str] = []
        self.loads: list[tuple[str, bigquery.LoadJobConfig, bytes]] = []
        self.queries: list[tuple[str, bigquery.QueryJobConfig]] = []
        self.newer = newer
        self.fail_query: Exception | None = None

    def get_table(self, table_id: str, **_: Any) -> Any:
        if table_id not in self.tables:
            raise api_exceptions.NotFound(table_id)
        return self.tables[table_id]

    def create_table(self, table: bigquery.Table, **_: Any) -> bigquery.Table:
        table_id = f"{table.project}.{table.dataset_id}.{table.table_id}"
        if table_id in self.tables:
            raise api_exceptions.Conflict(table_id)
        self.tables[table_id] = table
        self.created.append(table)
        return table

    def delete_table(self, table: Any, not_found_ok: bool = False, **_: Any) -> None:
        table_id = f"{table.project}.{table.dataset_id}.{table.table_id}"
        self.tables.pop(table_id, None)
        self.deleted.append(table_id)

    def load_table_from_file(self, data: Any, destination: Any, job_config: Any, **_: Any) -> Job:
        table_id = f"{destination.project}.{destination.dataset_id}.{destination.table_id}"
        self.loads.append((table_id, job_config, data.read()))
        return Job()

    def query(self, sql: str, job_config: bigquery.QueryJobConfig, **_: Any) -> Job:
        self.queries.append((sql, job_config))
        if self.fail_query:
            return Job(error=self.fail_query)
        if sql.startswith("select 1") and self.newer:
            return Job(rows=[(1,)])
        return Job()


def make(client: FakeClient) -> BigQueryWarehouse:
    return BigQueryWarehouse(lambda: client, maximum_bytes_billed=CAP)


def params(config: bigquery.QueryJobConfig) -> dict[str, Any]:
    return {p.name: p.value for p in config.query_parameters}


ROWS = [{"order_id": "o-1", "amount": "12.50"}, {"order_id": "o-2", "amount": 3}]


# The selector and its configuration.


def test_bigquery_is_chosen_by_elf_warehouse_and_needs_a_project():
    with pytest.raises(ConfigError, match="GCP_PROJECT is required"):
        Config.from_env({"ELF_WAREHOUSE": "bigquery"})

    config = Config.from_env(
        {"ELF_WAREHOUSE": "bigquery", "GCP_PROJECT": "lab", "GCP_ACCESS_TOKEN": "secret"}
    )
    chosen = warehouse(config)

    assert config.warehouse_dsn == ""  # no Postgres
    assert config.bigquery_maximum_bytes_billed == CAP
    assert "secret" not in repr(config)
    assert isinstance(chosen, BigQueryWarehouse)
    assert not isinstance(chosen, FileLedger)  # so the app serves no file source on it


def test_the_byte_cap_is_configurable_and_never_off():
    env = {"ELF_WAREHOUSE": "bigquery", "GCP_PROJECT": "lab"}
    assert Config.from_env({**env, "BQ_MAXIMUM_BYTES_BILLED": "1000"}).bigquery_maximum_bytes_billed
    with pytest.raises(ConfigError, match="BQ_MAXIMUM_BYTES_BILLED"):
        Config.from_env({**env, "BQ_MAXIMUM_BYTES_BILLED": "0"})


# Tables.


def test_ensure_creates_a_missing_table_with_the_metadata_columns():
    client = FakeClient()

    make(client).ensure_table(TABLE)

    (created,) = client.created
    assert created.table_id == "synthetic_orders"
    assert [(f.name, f.field_type, f.mode) for f in created.schema] == [
        ("order_id", "STRING", "NULLABLE"),
        ("amount", "NUMERIC", "NULLABLE"),
        ("_run_id", "STRING", "REQUIRED"),
        ("_interval_start", "TIMESTAMP", "REQUIRED"),
        ("_interval_end", "TIMESTAMP", "REQUIRED"),
        ("_page", "INT64", "REQUIRED"),
        ("_source_uri", "STRING", "REQUIRED"),
        ("_loaded_at", "TIMESTAMP", "NULLABLE"),
    ]


def test_ensure_leaves_an_existing_table_alone():
    client = FakeClient(existing={"lab-project.ds_source.synthetic_orders"})

    make(client).ensure_table(TABLE)

    assert client.created == []


def test_a_file_table_is_keyed_by_object_and_generation():
    client = FakeClient()

    make(client).ensure_file_table(TABLE)

    names = [f.name for f in client.created[0].schema]
    assert names[2:] == ["_run_id", "_source_uri", "_generation", "_loaded_at"]


def test_an_unknown_column_type_is_refused():
    with pytest.raises(WarehouseError, match="no BigQuery type") as e:
        make(FakeClient()).ensure_table(Table("t", (("x", "money"),)))
    assert e.value.transient is False


# Page loads.


def test_a_page_is_loaded_by_a_load_job_into_staging_then_replaced_in_one_transaction():
    client = FakeClient()
    load = PageLoad("scheduled__2025-10-01T00:00:00+00:00", DAY, 0, "gs://staging/p-00000.jsonl")

    assert make(client).replace_page(TABLE, load, ROWS) == 2

    (staging,) = client.created
    assert staging.table_id.startswith("elf_staging_synthetic_orders_")
    assert staging.expires is not None
    (target, config, body) = client.loads[0]
    assert target == f"lab-project.ds_source.{staging.table_id}"
    assert config.source_format == "NEWLINE_DELIMITED_JSON"
    assert config.write_disposition == "WRITE_APPEND"
    assert config.labels == {
        "component": "el-factory",
        "purpose": "stage",
        "table": "synthetic_orders",
        "run": "scheduled__2025-10-01t00_00_00_00_00",
    }
    # The staged rows carry the load's metadata, all but _loaded_at, which the copy stamps.
    assert [json.loads(line) for line in body.splitlines()] == [
        {
            **row,
            "_run_id": load.run_id,
            "_interval_start": "2025-10-01 00:00:00+00:00",
            "_interval_end": "2025-10-02 00:00:00+00:00",
            "_page": 0,
            "_source_uri": load.source_uri,
        }
        for row in ROWS
    ]
    (sql, job) = client.queries[0]
    assert sql.startswith("begin transaction;") and sql.endswith("commit transaction;")
    assert f"from `{target}`" in sql
    assert "current_timestamp()" in sql
    assert "_page = @page" not in sql  # page 0 clears the run's whole interval
    assert job.maximum_bytes_billed == CAP
    assert job.labels["purpose"] == "replace-page"
    assert params(job) == {
        "run_id": load.run_id,
        "interval_start": DAY.start,
        "interval_end": DAY.end,
    }
    assert client.deleted == [target]  # the staging table goes


def test_a_later_page_replaces_only_itself():
    client = FakeClient()

    make(client).replace_page(TABLE, PageLoad("r", DAY, 3, "gs://b/p"), ROWS)

    delete = client.queries[0][0].split("insert")[0]
    assert "_page = @page" in delete
    assert params(client.queries[0][1])["page"] == 3


def test_an_empty_page_still_clears_its_scope_without_a_load():
    client = FakeClient()

    assert make(client).replace_page(TABLE, PageLoad("r", DAY, 0, "gs://b/p"), []) == 0

    assert client.loads == []
    assert "delete from" in client.queries[0][0]


def test_the_staging_table_goes_when_the_replace_fails():
    client = FakeClient()
    client.fail_query = api_exceptions.BadRequest("Syntax error")

    with pytest.raises(WarehouseError):
        make(client).replace_page(TABLE, PageLoad("r", DAY, 0, "gs://b/p"), ROWS)

    assert len(client.deleted) == 1
    assert client.tables == {}


# File loads.


def test_a_file_replaces_its_object_unless_a_newer_generation_is_loaded():
    client = FakeClient()
    load = FileLoad("r", "gs://landing/returns.ndjson", 42)

    assert make(client).replace_file(TABLE, load, ROWS) == 2

    check, replace = client.queries
    assert check[0].startswith("select 1") and check[1].maximum_bytes_billed == CAP
    assert "_generation <= @generation" in replace[0]
    assert "and not exists (select 1" in replace[0]  # a newer generation that committed first
    assert params(replace[1]) == {"source_uri": load.source_uri, "generation": 42}
    staged = [json.loads(line) for line in client.loads[0][2].splitlines()]
    assert staged[0] == {
        **ROWS[0],
        "_run_id": "r",
        "_source_uri": load.source_uri,
        "_generation": 42,
    }


def test_a_superseded_generation_writes_nothing():
    client = FakeClient(newer=True)

    assert make(client).replace_file(TABLE, FileLoad("r", "gs://l/x", 1), ROWS) is None

    assert client.loads == [] and client.created == [] and len(client.queries) == 1


# Errors.


@pytest.mark.parametrize(
    ("error", "transient"),
    [
        (api_exceptions.ServiceUnavailable("down"), True),
        (api_exceptions.InternalServerError("oops"), True),
        (api_exceptions.TooManyRequests("slow down"), True),
        (api_exceptions.Forbidden("Exceeded rate limits: rateLimitExceeded"), True),
        (api_exceptions.BadRequest("Transaction is aborted due to concurrent update"), True),
        (requests.ConnectionError("refused"), True),
        (api_exceptions.BadRequest("Syntax error: unexpected keyword"), False),
        (api_exceptions.Forbidden("Access Denied: Table"), False),
        (api_exceptions.BadRequest("Query exceeded limit for bytes billed"), False),
    ],
)
def test_client_errors_are_warehouse_errors(error, transient):
    client = FakeClient()
    client.fail_query = error

    with pytest.raises(WarehouseError) as e:
        make(client).replace_page(TABLE, PageLoad("r", DAY, 0, "gs://b/p"), [])

    assert e.value.transient is transient


def test_the_client_is_built_on_first_use():
    built: list[int] = []

    def connect() -> FakeClient:
        built.append(1)
        return FakeClient()

    store = BigQueryWarehouse(connect, maximum_bytes_billed=CAP)
    assert built == []
    store.ensure_table(TABLE)
    assert built == [1]


def test_labels_follow_bigquerys_rules():
    assert (
        warehouse_bigquery.label("Manual__2025-10-01T00:00:00+00:00" * 3)
        == ("manual__2025-10-01t00_00_00_00_00" * 3)[:63]
    )
