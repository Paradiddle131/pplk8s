import json
from datetime import UTC, datetime

import psycopg
import pytest
from google.api_core import exceptions as gcs_exceptions

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


def test_catalog_lists_the_marketing_pipeline(client):
    response = client.get("/catalog?pipeline=marketing")

    assert response.status_code == 200
    assert response.get_json() == [
        {"source": "synthetic", "entity": entity}
        for entity in ("campaigns", "ad_spend", "leads", "bookings")
    ]


def test_catalog_lists_the_customer_actions_pipeline(client):
    response = client.get("/catalog?pipeline=customer_actions")

    assert response.status_code == 200
    assert response.get_json() == [{"source": "synthetic", "entity": "customer_actions"}]


def test_catalog_lists_the_partner_outreach_pipeline(client):
    response = client.get("/catalog?pipeline=partner_outreach")

    assert response.status_code == 200
    assert response.get_json() == [
        {"source": "synthetic", "entity": "partners"},
        {"source": "synthetic", "entity": "partner_contacts"},
        {"source": "synthetic", "entity": "outreach_messages"},
        {"source": "synthetic", "entity": "outreach_replies"},
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
        "pages": 1,
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

        ensure_file_table = ensure_table

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
        "partner_returns",
        "synthetic_ad_spend",
        "synthetic_bookings",
        "synthetic_campaigns",
        "synthetic_customer_actions",
        "synthetic_customers",
        "synthetic_leads",
        "synthetic_orders",
        "synthetic_outreach_messages",
        "synthetic_outreach_replies",
        "synthetic_partner_contacts",
        "synthetic_partners",
    ]


SOURCE_TABLES = [
    "open_meteo_hourly_weather",
    "partner_returns",
    "synthetic_ad_spend",
    "synthetic_bookings",
    "synthetic_campaigns",
    "synthetic_customer_actions",
    "synthetic_customers",
    "synthetic_leads",
    "synthetic_orders",
    "synthetic_outreach_messages",
    "synthetic_outreach_replies",
    "synthetic_partner_contacts",
    "synthetic_partners",
]


def test_an_extract_after_a_warehouse_reset_recreates_every_source_table(make_client, warehouse):
    # Issue #172: the warehouse is reset under a running service, then sales extracts orders;
    # sales' dbt build also reads the weather table, which no sales extract names.
    client = make_client()
    warehouse.ensured.clear()

    assert client.post("/extract", json=ORDERS_BODY).status_code == 200

    assert sorted(set(warehouse.ensured)) == SOURCE_TABLES


def test_startup_survives_an_unreachable_warehouse(storage):
    class DownWarehouse:
        def ensure_table(self, table):
            raise OSError("connection refused")

        ensure_file_table = ensure_table

        def replace_page(self, table, load, rows):
            raise AssertionError("not called")

    app = create_app(make_config(), storage, DownWarehouse())

    assert app.test_client().get("/healthz").status_code == 200


def test_transient_warehouse_error_is_a_retryable_503(make_client, storage):
    class FlakyWarehouse:
        def ensure_table(self, table):
            pass

        ensure_file_table = ensure_table

        def replace_page(self, table, load, rows):
            raise psycopg.OperationalError("server closed the connection unexpectedly")

    app = create_app(make_config(), storage, FlakyWarehouse())
    app.config["TESTING"] = False

    response = app.test_client().post("/extract", json=ORDERS_BODY)

    assert response.status_code == 503
    assert response.get_json()["retryable"] is True


def test_transient_storage_error_is_a_retryable_503(make_client, storage, monkeypatch):
    def unavailable(uri, data):
        raise gcs_exceptions.ServiceUnavailable("try again")

    monkeypatch.setattr(storage, "upload", unavailable)

    response = post(make_client(), ORDERS_BODY)

    assert response.status_code == 503
    assert response.get_json()["retryable"] is True


def test_page_zero_replaces_every_page_of_the_same_run_and_interval(make_client, warehouse):
    def run(client):
        url = "/extract"
        while url:
            url = post(client, ORDERS_BODY, url).get_json()["next_url"]

    run(make_client(page_size=20))
    run(make_client(page_size=100))

    assert warehouse.row_count("synthetic_orders") == expected_orders()


def test_catalog_omits_disabled_entries(make_client, tmp_path):
    catalog = tmp_path / "catalog.yaml"
    catalog.write_text(
        "pipelines:\n"
        "  sales:\n"
        "    - {source: synthetic, entity: customers}\n"
        "    - {source: synthetic, entity: orders, enabled: false}\n"
    )

    response = make_client(catalog_path=catalog).get("/catalog?pipeline=sales")

    assert response.get_json() == [{"source": "synthetic", "entity": "customers"}]


class FakeClock:
    """Each read advances by one second, so a budget of N seconds allows about N pages."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 1.0
        return self.now


def test_a_request_works_until_its_budget_and_answers_next_url(make_client, warehouse):
    client = make_client(page_size=1, max_run_time=3.0, clock=FakeClock())

    response = post(client, ORDERS_BODY).get_json()

    assert response["page"] == 0
    assert response["pages"] == 3
    assert response["rows"] == 3
    assert response["next_url"] == "/extract?cursor=3"
    assert warehouse.row_count("synthetic_orders") == 3


def test_continuations_load_every_row_once_and_a_retry_starts_over(make_client, warehouse):
    client = make_client(page_size=1, max_run_time=2.0, clock=FakeClock())

    def run() -> list[dict]:
        responses = [post(client, ORDERS_BODY).get_json()]
        while responses[-1]["next_url"] is not None:
            responses.append(post(client, ORDERS_BODY, path=responses[-1]["next_url"]).get_json())
        return responses

    first = run()
    retry = run()

    assert len(first) >= 2
    assert sum(r["rows"] for r in first) == expected_orders()
    assert [r["page"] for r in retry] == [r["page"] for r in first]
    assert warehouse.row_count("synthetic_orders") == expected_orders()


def test_a_zero_budget_answers_one_page_per_request(make_client):
    client = make_client(page_size=10, max_run_time=0.0)

    response = post(client, ORDERS_BODY).get_json()

    assert response["pages"] == 1
    assert response["next_url"] == "/extract?cursor=1"


def test_a_large_budget_finishes_in_one_request(make_client, warehouse):
    client = make_client(page_size=10, max_run_time=3600.0)

    response = post(client, ORDERS_BODY).get_json()

    assert response["next_url"] is None
    assert response["rows"] == expected_orders()
    assert warehouse.row_count("synthetic_orders") == expected_orders()
