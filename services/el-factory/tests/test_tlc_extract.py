"""The tlc file source end to end against the Compose warehouse (make services-up).

Tables land in a throwaway schema, and the chunk ledger rows are keyed by the local server's URLs,
so the lab's own data is never touched.
"""

import os
import uuid
from datetime import datetime

import psycopg
import pytest
from google.api_core import exceptions as gcs_exceptions

from el_factory.app import create_app
from el_factory.warehouse import PostgresWarehouse
from tests.conftest import FakeStorage, make_config
from tests.tlc_fixtures import TlcServer, retyped_flag, yellow_2023, yellow_2025

DSN = os.environ.get(
    "TEST_WAREHOUSE_DSN", "postgresql://warehouse:warehouse@localhost:5433/warehouse"
)
OCT = datetime(2025, 10, 1)


def month_body(month: str, end: str) -> dict:
    return {
        "source": "tlc",
        "entity": "yellow",
        "run_id": "scheduled__test",
        "interval_start": f"{month}-01T00:00:00+00:00",
        "interval_end": f"{end}-01T00:00:00+00:00",
    }


OCT_BODY = month_body("2025-10", "2025-11")


@pytest.fixture
def db():
    schema = f"test_tlc_{uuid.uuid4().hex[:8]}"
    try:
        conn = psycopg.connect(DSN, autocommit=True, connect_timeout=3)
        conn.execute("SELECT 1 FROM ops.file_chunks LIMIT 1")
    except Exception as exc:  # noqa: BLE001 - any connectivity problem means no warehouse here
        message = f"warehouse with ops.file_chunks not reachable (make services-up): {exc}"
        if os.environ.get("PPLK8S_REQUIRE_WAREHOUSE") == "1":
            pytest.fail(message)
        pytest.skip(message)
    conn.execute(f'CREATE SCHEMA "{schema}"')
    yield conn, schema
    conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
    conn.close()


@pytest.fixture
def server(db):
    tlc = TlcServer()
    yield tlc
    conn, _ = db
    for table in ("ops.file_chunks", "ops.file_versions"):
        conn.execute(f"DELETE FROM {table} WHERE source_uri LIKE %s", [tlc.base_url + "/%"])
    tlc.close()


class FailingStorage(FakeStorage):
    """Fails the upload of one chunk once, like a GCS 503 mid-month."""

    def __init__(self, fail_on: str) -> None:
        super().__init__()
        self.fail_on = fail_on

    def upload(self, uri: str, data: bytes) -> int:
        if uri.endswith(self.fail_on):
            self.fail_on = "never"
            raise gcs_exceptions.ServiceUnavailable("injected")
        return super().upload(uri, data)


@pytest.fixture
def make_tlc_client(db, server):
    _, schema = db

    def build(max_run_time: float = 3600.0, storage: FakeStorage | None = None):
        config = make_config(tlc_base_url=server.base_url, max_run_time=max_run_time)
        app = create_app(config, storage or FakeStorage(), PostgresWarehouse(DSN, schema=schema))
        app.config["TESTING"] = True
        return app.test_client()

    return build


def landed(db, where: str = "TRUE") -> list[tuple]:
    conn, schema = db
    return conn.execute(
        f'SELECT _etag, _chunk, count(*) FROM "{schema}".tlc_yellow WHERE {where}'
        " GROUP BY 1, 2 ORDER BY 1, 2"
    ).fetchall()


def follow(client, body: dict) -> list[dict]:
    responses = [client.post("/extract", json=body).get_json()]
    while responses[-1].get("next_url"):
        responses.append(client.post(responses[-1]["next_url"], json=body).get_json())
    return responses


def test_a_month_loads_in_chunks_under_a_tiny_budget(db, server, make_tlc_client):
    url = server.publish("yellow_tripdata_2025-10.parquet", yellow_2025(12, 4, OCT))
    client = make_tlc_client(max_run_time=0.0)

    responses = follow(client, OCT_BODY)

    assert [r["pages"] for r in responses] == [1, 1, 1]
    assert [r["page"] for r in responses] == [0, 1, 2]
    assert sum(r["rows"] for r in responses) == 12
    assert [count for _, _, count in landed(db)] == [4, 4, 4]
    conn, _ = db
    assert conn.execute(
        "SELECT count(*) FROM ops.file_versions WHERE source_uri = %s", [url]
    ).fetchone() == (1,)


def test_a_retry_resumes_after_the_loaded_chunks(db, server, make_tlc_client):
    server.publish("yellow_tripdata_2025-10.parquet", yellow_2025(12, 4, OCT))
    client = make_tlc_client(storage=FailingStorage(fail_on="chunk-00002.parquet"))

    failed = client.post("/extract", json=OCT_BODY)
    assert failed.status_code == 503
    assert failed.get_json()["retryable"] is True
    assert [chunk for _, chunk, _ in landed(db)] == [0, 1]

    retry = client.post("/extract", json=OCT_BODY).get_json()  # a new attempt: no cursor

    assert (retry["page"], retry["pages"], retry["rows"], retry["next_url"]) == (2, 1, 4, None)
    assert [count for _, _, count in landed(db)] == [4, 4, 4]


def test_a_finished_month_is_a_no_op(db, server, make_tlc_client):
    server.publish("yellow_tripdata_2025-10.parquet", yellow_2025(8, 4, OCT))
    client = make_tlc_client()
    follow(client, OCT_BODY)

    again = client.post("/extract", json=OCT_BODY).get_json()

    assert (again["pages"], again["rows"], again["next_url"]) == (0, 0, None)
    assert [count for _, _, count in landed(db)] == [4, 4]


def test_a_republished_file_reloads_and_replaces_its_month(db, server, make_tlc_client):
    server.publish("yellow_tripdata_2025-10.parquet", yellow_2025(12, 4, OCT))
    client = make_tlc_client()
    first = follow(client, OCT_BODY)[-1]["etag"]

    server.publish("yellow_tripdata_2025-10.parquet", yellow_2023(6, 4, OCT))
    second = follow(client, OCT_BODY)

    assert second[0]["etag"] != first
    assert second[0]["page"] == 0
    assert landed(db) == [(second[0]["etag"], 0, 4), (second[0]["etag"], 1, 2)]


def test_a_newer_schema_adds_columns_without_touching_earlier_rows(db, server, make_tlc_client):
    server.publish("yellow_tripdata_2023-12.parquet", yellow_2023(6, 4, datetime(2023, 12, 1)))
    server.publish("yellow_tripdata_2025-01.parquet", yellow_2025(5, 4, datetime(2025, 1, 1)))
    client = make_tlc_client()

    follow(client, month_body("2023-12", "2024-01"))
    follow(client, month_body("2025-01", "2025-02"))

    conn, schema = db
    types = dict(
        conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns"
            " WHERE table_schema = %s AND table_name = 'tlc_yellow'",
            [schema],
        ).fetchall()
    )
    assert types["cbd_congestion_fee"] == "double precision"
    assert types["airport_fee"] == "double precision"  # 2023 airport_fee and 2025 Airport_fee
    assert types["vendorid"] == "bigint"  # int64 in 2023; the int32 of 2025 fits
    assert types["passenger_count"] == "double precision"  # double in 2023, int64 in 2025
    assert "ehail_fee" not in types  # all-null: nothing to learn from it yet
    rows = conn.execute(
        f"SELECT _source_uri LIKE %s, count(*), count(cbd_congestion_fee), sum(airport_fee)"
        f' FROM "{schema}".tlc_yellow GROUP BY 1 ORDER BY 1',
        ["%2025-01%"],
    ).fetchall()
    assert rows == [(False, 6, 0, 0.0), (True, 5, 5, 8.75)]


def test_widening_keeps_the_views_that_read_the_landing_table(db, server, make_tlc_client):
    # dbt's bronze views read the landing table; Postgres refuses to retype a column a view uses,
    # while BigQuery's late-binding views never notice a relaxed column (#72).
    server.publish("yellow_tripdata_2025-01.parquet", yellow_2025(5, 4, datetime(2025, 1, 1)))
    server.publish("yellow_tripdata_2023-12.parquet", yellow_2023(6, 4, datetime(2023, 12, 1)))
    client = make_tlc_client()
    follow(client, month_body("2025-01", "2025-02"))
    conn, schema = db
    conn.execute(
        f'CREATE VIEW "{schema}".bronze AS SELECT cast(passenger_count AS bigint) AS passengers,'
        f' vendorid, _source_uri FROM "{schema}".tlc_yellow'
    )
    conn.execute(
        f'CREATE VIEW "{schema}".bronze_count AS SELECT count(*) AS n FROM "{schema}".bronze'
    )

    responses = follow(client, month_body("2023-12", "2024-01"))

    assert responses[-1]["status"] == "ok", responses[-1]
    types = dict(
        conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns"
            " WHERE table_schema = %s AND table_name = 'tlc_yellow'",
            [schema],
        ).fetchall()
    )
    assert types["passenger_count"] == "double precision"
    assert types["vendorid"] == "bigint"
    assert conn.execute(f'SELECT n FROM "{schema}".bronze_count').fetchone() == (11,)
    view_types = dict(
        conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns"
            " WHERE table_schema = %s AND table_name = 'bronze'",
            [schema],
        ).fetchall()
    )
    # The views keep the column types they had; the next dbt build of bronze re-derives them.
    assert view_types == {"passengers": "bigint", "vendorid": "integer", "_source_uri": "text"}


def test_an_incompatible_retype_fails_without_retry(db, server, make_tlc_client):
    server.publish("yellow_tripdata_2025-10.parquet", yellow_2025(4, 4, OCT))
    server.publish("yellow_tripdata_2025-11.parquet", retyped_flag(4, datetime(2025, 11, 1)))
    client = make_tlc_client()
    follow(client, OCT_BODY)

    response = client.post("/extract", json=month_body("2025-11", "2025-12"))

    assert response.status_code == 502
    assert response.get_json()["retryable"] is False
    assert "store_and_fwd_flag" in response.get_json()["error"]


def test_a_chunk_over_the_memory_budget_fails_without_retry(
    db, server, make_tlc_client, monkeypatch
):
    # FHVHV 2023-01 is one 451 MiB row group: staging it peaks at ~1.5 GiB, so EL Factory refuses
    # it up front instead of being OOMKilled on every retry (D35, #90).
    server.publish("yellow_tripdata_2025-10.parquet", yellow_2025(12, 4, OCT))
    monkeypatch.setattr("el_factory.chunks.MAX_CHUNK_BYTES", 64)
    client = make_tlc_client()

    response = client.post("/extract", json=OCT_BODY)

    assert response.status_code == 422
    assert response.get_json()["retryable"] is False
    assert "chunk 0" in response.get_json()["error"]
    conn, schema = db
    assert conn.execute(  # refused before the landing table is created
        "SELECT to_regclass(%s)", [f'"{schema}".tlc_yellow']
    ).fetchone() == (None,)


def test_an_unpublished_month_is_a_non_retryable_502(db, server, make_tlc_client):
    response = make_tlc_client().post("/extract", json=month_body("2099-01", "2099-02"))

    assert response.status_code == 502
    assert response.get_json() == {
        "status": "error",
        "retryable": False,
        "error": f"{server.base_url}/yellow_tripdata_2099-01.parquet: "
        "not published (S3 AccessDenied)",
        "published": False,
    }


# ---- retention (D35, issue #87) -----------------------------------------------------------------


def load_months(server, client, *months: str) -> None:
    for month in months:
        start = datetime.fromisoformat(f"{month}-01")
        end = f"{start.year + start.month // 12:04d}-{start.month % 12 + 1:02d}"
        server.publish(f"yellow_tripdata_{month}.parquet", yellow_2025(6, 4, start))
        follow(client, month_body(month, end))


def held(client) -> list[str]:
    response = client.get("/months", query_string={"source": "tlc", "entity": "yellow"})
    assert response.status_code == 200
    return response.get_json()["months"]


def test_months_lists_the_loaded_and_the_half_loaded_months(db, server, make_tlc_client):
    client = make_tlc_client()
    load_months(server, client, "2025-09", "2025-10")
    server.publish("yellow_tripdata_2025-11.parquet", yellow_2025(12, 4, datetime(2025, 11, 1)))
    partial = make_tlc_client(max_run_time=0.0).post(
        "/extract", json=month_body("2025-11", "2025-12")
    )
    assert partial.get_json()["next_url"] is not None  # one chunk of three, no file_versions row

    assert held(client) == ["2025-09", "2025-10", "2025-11"]


def test_retire_drops_every_month_outside_keep_from_landing_and_the_ledgers(
    db, server, make_tlc_client
):
    client = make_tlc_client(max_run_time=3600.0)
    load_months(server, client, "2025-08", "2025-09", "2025-10")
    conn, _ = db

    response = client.post(
        "/retire", json={"source": "tlc", "entity": "yellow", "keep": ["2025-09", "2025-10"]}
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["retired"] == [{"month": "2025-08", "rows": 6}]
    assert body["rows"] == 6
    assert held(client) == ["2025-09", "2025-10"]
    assert [c for _, _, c in landed(db)] == [4, 2, 4, 2]
    stale = f"{server.base_url}/yellow_tripdata_2025-08.parquet"
    for table in ("ops.file_chunks", "ops.file_versions"):
        assert conn.execute(
            f"SELECT count(*) FROM {table} WHERE source_uri = %s", [stale]
        ).fetchone() == (0,)


def test_a_retired_month_reloads_from_scratch(db, server, make_tlc_client):
    client = make_tlc_client(max_run_time=3600.0)
    load_months(server, client, "2025-09", "2025-10")
    client.post("/retire", json={"source": "tlc", "entity": "yellow", "keep": ["2025-10"]})

    reload = follow(client, month_body("2025-09", "2025-10"))

    assert (reload[0]["page"], sum(r["rows"] for r in reload)) == (0, 6)
    assert held(client) == ["2025-09", "2025-10"]


def test_retire_is_a_no_op_when_everything_is_kept(db, server, make_tlc_client):
    client = make_tlc_client(max_run_time=3600.0)
    load_months(server, client, "2025-10")

    body = client.post(
        "/retire", json={"source": "tlc", "entity": "yellow", "keep": ["2025-10", "2023-01"]}
    ).get_json()

    assert (body["retired"], body["rows"]) == ([], 0)
    assert [c for _, _, c in landed(db)] == [4, 2]


@pytest.mark.parametrize(
    "keep", [None, [], "2025-10", ["2025-13"], ["2025-1"], [202510], ["2025-10", None]]
)
def test_retire_refuses_a_missing_or_malformed_keep(db, server, make_tlc_client, keep):
    client = make_tlc_client()
    load_months(server, client, "2025-10")
    body = {"source": "tlc", "entity": "yellow"}
    if keep is not None:
        body["keep"] = keep

    response = client.post("/retire", json=body)

    assert response.status_code == 400
    assert response.get_json()["retryable"] is False
    assert held(client) == ["2025-10"]


def test_retention_refuses_a_paged_source(db, server, make_tlc_client):
    client = make_tlc_client()

    assert client.get("/months?source=synthetic&entity=orders").status_code == 400
    response = client.post(
        "/retire", json={"source": "synthetic", "entity": "orders", "keep": ["2025-10"]}
    )
    assert response.status_code == 400
