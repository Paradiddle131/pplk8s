import json
from datetime import UTC, datetime

import pytest

from el_factory.app import create_app
from el_factory.model import Interval
from el_factory.sources.synthetic import build_orders
from el_factory.staging import object_uri
from tests.conftest import make_config

ORDERS_BODY = {
    "source": "synthetic",
    "entity": "orders",
    "run_id": "dev__1",
    "interval_start": "2026-10-01T00:00:00+00:00",
    "interval_end": "2026-10-03T00:00:00+00:00",
}


def post(client, body, path="/extract"):
    return client.post(path, json=body)


def expected_orders() -> int:
    interval = Interval(datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 3, tzinfo=UTC))
    return len(build_orders(interval))


def test_healthz_is_ok_without_dependencies(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_catalog_lists_the_pipeline_entries(client):
    response = client.get("/catalog?pipeline=sales")

    assert response.status_code == 200
    assert response.get_json() == [
        {"source": "synthetic", "entity": "customers"},
        {"source": "synthetic", "entity": "orders"},
    ]


def test_catalog_requires_a_pipeline_parameter(client):
    response = client.get("/catalog")

    assert response.status_code == 400
    assert response.get_json()["retryable"] is False


def test_catalog_rejects_an_unknown_pipeline(client):
    response = client.get("/catalog?pipeline=nope")

    assert response.status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        {"source": None},
        {"entity": ""},
        {"run_id": "bad run id"},
        {"run_id": "x/../y"},
        {"interval_start": "2026-10-01T00:00:00"},
        {"interval_start": "not-a-time"},
        {
            "interval_start": "2026-10-03T00:00:00+00:00",
            "interval_end": "2026-10-01T00:00:00+00:00",
        },
        {"interval_end": "2026-10-01T00:00:00+00:00"},
        {"cursor": "-1"},
        {"cursor": "abc"},
    ],
)
def test_malformed_extract_requests_are_400(client, change):
    body = {**ORDERS_BODY, **change}

    response = post(client, body)

    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_non_object_body_is_400(client):
    response = client.post("/extract", data="[]", content_type="application/json")

    assert response.status_code == 400


def test_unknown_source_and_entity_are_404(client):
    assert post(client, {**ORDERS_BODY, "source": "nope"}).status_code == 404
    assert post(client, {**ORDERS_BODY, "entity": "nope"}).status_code == 404


def test_extract_stages_and_loads_every_page_then_stops(client, storage, warehouse):
    first = post(client, {**ORDERS_BODY, "cursor": None}).get_json()
    pages = [first]
    while pages[-1]["next_url"] is not None:
        pages.append(post(client, ORDERS_BODY, path=pages[-1]["next_url"]).get_json())

    assert pages[0]["page"] == 0
    assert pages[0]["object"] == ("gs://staging/synthetic/orders/dev__1/page-00000.jsonl")
    assert [p["page"] for p in pages] == list(range(len(pages)))
    assert sum(p["rows"] for p in pages) == expected_orders()
    assert pages[-1]["next_url"] is None
    assert len(storage.objects) == len(pages)
    assert warehouse.row_count("synthetic_orders") == expected_orders()


def test_page_size_controls_the_number_of_pages(make_client, warehouse):
    client = make_client(page_size=10)
    total = expected_orders()

    response = post(client, ORDERS_BODY).get_json()

    assert response["rows"] == min(10, total)
    assert response["next_url"] == "/extract?cursor=1"


def test_query_cursor_wins_over_body_cursor(client):
    response = post(client, {**ORDERS_BODY, "cursor": "5"}, path="/extract?cursor=0").get_json()

    assert response["page"] == 0


def test_body_cursor_is_used_without_query(make_client):
    client = make_client(page_size=1)

    response = post(client, {**ORDERS_BODY, "cursor": "1"}).get_json()

    assert response["page"] == 1
    assert response["object"].endswith("/page-00001.jsonl")


def test_empty_interval_stages_an_empty_page_and_stops(client, storage, warehouse):
    body = {
        **ORDERS_BODY,
        "interval_start": "2026-10-01T00:00:00+00:00",
        "interval_end": "2026-10-01T00:00:01+00:00",
    }

    response = post(client, body).get_json()

    assert (
        build_orders(
            Interval(datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 10, 1, 0, 0, 1, tzinfo=UTC))
        )
        == []
    )
    assert response == {
        "status": "ok",
        "source": "synthetic",
        "entity": "orders",
        "page": 0,
        "rows": 0,
        "object": "gs://staging/synthetic/orders/dev__1/page-00000.jsonl",
        "next_url": None,
    }
    assert storage.objects[response["object"]] == b""


def test_rerunning_the_same_request_leaves_row_counts_unchanged(client, warehouse):
    first = post(client, ORDERS_BODY).get_json()
    count = warehouse.row_count("synthetic_orders")

    second = post(client, ORDERS_BODY).get_json()

    assert second["rows"] == first["rows"]
    assert warehouse.row_count("synthetic_orders") == count


def test_staged_object_is_the_source_of_the_loaded_rows(client, storage, warehouse):
    post(client, ORDERS_BODY)
    uri = object_uri("staging", "synthetic", "orders", "dev__1", 0)
    staged = [json.loads(line) for line in storage.objects[uri].decode().splitlines()]

    loaded = next(iter(warehouse.tables["synthetic_orders"].values()))

    assert [row["order_id"] for row in loaded] == [row["order_id"] for row in staged]
    assert all(row["_source_uri"] == uri for row in loaded)


def test_fail_rate_one_returns_retryable_503_before_any_work(make_client, storage, warehouse):
    client = make_client(fail_rate=1.0)

    response = post(client, ORDERS_BODY)

    assert response.status_code == 503
    assert response.get_json() == {
        "status": "error",
        "retryable": True,
        "error": "injected transient failure (FAIL_RATE)",
    }
    assert storage.objects == {}
    assert warehouse.row_count("synthetic_orders") == 0


def test_unexpected_failures_are_500_and_not_retryable(make_client, storage):
    class BrokenWarehouse:
        def ensure_table(self, table):
            pass

        def replace_page(self, table, load, rows):
            raise RuntimeError("warehouse exploded")

    app = create_app(make_config(), storage, BrokenWarehouse())
    app.config["TESTING"] = False

    response = app.test_client().post("/extract", json=ORDERS_BODY)

    assert response.status_code == 500
    assert response.get_json() == {"status": "error", "retryable": False, "error": "internal error"}


def test_startup_provisions_every_source_table(make_client, warehouse):
    make_client()

    assert sorted(set(warehouse.ensured)) == [
        "open_meteo_hourly_weather",
        "synthetic_customers",
        "synthetic_orders",
    ]


def test_startup_survives_an_unreachable_warehouse(storage):
    class DownWarehouse:
        def ensure_table(self, table):
            raise OSError("connection refused")

        def replace_page(self, table, load, rows):
            raise AssertionError("not called")

    app = create_app(make_config(), storage, DownWarehouse())

    assert app.test_client().get("/healthz").status_code == 200
