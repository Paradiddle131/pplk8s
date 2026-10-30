import os
from datetime import UTC, datetime

import pytest
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk.exceptions import AirflowFailException
from pplk8s import readiness

START = datetime(2026, 10, 8, tzinfo=UTC)
END = datetime(2026, 10, 9, tzinfo=UTC)


def _warehouse_unreachable(what: str, exc: Exception):
    """Skip on a laptop without `make services-up`; fail where CI promised a warehouse."""
    message = f"{what} not reachable at localhost:5433 (make services-up): {exc}"
    if os.environ.get("PPLK8S_REQUIRE_WAREHOUSE") == "1":
        pytest.fail(message)
    pytest.skip(message)


def test_upsert_sql_is_keyed_on_the_ledger_primary_key():
    sql = " ".join(readiness.UPSERT_SQL.split())
    assert "ON CONFLICT (product, interval_start, interval_end) DO UPDATE" in sql
    assert "updated_at = now()" in sql


def test_record_readiness_passes_parameters(mocker):
    run = mocker.patch.object(PostgresHook, "run")
    readiness.record_readiness("sales.gold", START, END, END, "run-1", "ready", dag_id="sales_elt")
    run.assert_called_once()
    assert run.call_args.args[0] == readiness.UPSERT_SQL
    assert run.call_args.kwargs["parameters"] == {
        "product": "sales.gold",
        "interval_start": START,
        "interval_end": END,
        "watermark": END,
        "dag_id": "sales_elt",
        "run_id": "run-1",
        "status": "ready",
    }


def test_marketing_extraction_has_a_watermark(mocker):
    lead, booking = (
        datetime(2026, 10, 1, 19, 5, tzinfo=UTC),
        datetime(2026, 10, 1, 17, 0, tzinfo=UTC),
    )
    get_first = mocker.patch.object(
        PostgresHook, "get_first", side_effect=[(8, None), (8, None), (190, lead), (12, booking)]
    )
    result = readiness.check_extraction(
        [
            {"source": "synthetic", "entity": entity, "pages": 1, "rows": rows}
            for entity, rows in (
                ("campaigns", 8),
                ("ad_spend", 8),
                ("leads", 190),
                ("bookings", 12),
            )
        ],
        "run-1",
        START,
        END,
    )
    assert result["watermark"] == lead.isoformat()
    assert "max(created_ts)" in get_first.call_args_list[2].args[0]
    assert "max(booked_ts)" in get_first.call_args_list[3].args[0]


def test_check_extraction_matches_rows_and_returns_watermark(mocker):
    latest = datetime(2026, 10, 8, 23, 59, tzinfo=UTC)
    get_first = mocker.patch.object(
        PostgresHook, "get_first", side_effect=[(200, None), (150, latest)]
    )
    result = readiness.check_extraction(
        [
            {"source": "synthetic", "entity": "customers", "pages": 2, "rows": 200},
            {"source": "synthetic", "entity": "orders", "pages": 2, "rows": 150},
        ],
        "run-1",
        START,
        END,
    )
    assert result == {
        "watermark": latest.isoformat(),
        "rows": {"synthetic_customers": 200, "synthetic_orders": 150},
    }
    assert "max(order_ts)" in get_first.call_args_list[1].args[0]
    assert "ds_source.synthetic_orders" in get_first.call_args_list[1].args[0]


def test_check_extraction_fails_fast_on_row_mismatch(mocker):
    mocker.patch.object(PostgresHook, "get_first", return_value=(10, None))
    with pytest.raises(AirflowFailException, match="reported 11"):
        readiness.check_extraction(
            [{"source": "synthetic", "entity": "customers", "pages": 1, "rows": 11}],
            "run-1",
            START,
            END,
        )


def test_check_extraction_rejects_empty_and_unsafe_input():
    with pytest.raises(AirflowFailException):
        readiness.check_extraction([], "run-1", START, END)
    with pytest.raises(AirflowFailException):
        readiness.table_for("x; drop table y", "z")


@pytest.fixture
def warehouse():
    hook = PostgresHook(postgres_conn_id="warehouse")
    try:
        hook.get_first("SELECT 1 FROM ops.readiness LIMIT 1")
    except Exception as exc:  # noqa: BLE001 - any connectivity problem means no warehouse here
        _warehouse_unreachable("warehouse", exc)
    hook.run("DELETE FROM ops.readiness WHERE product = 'test.readiness'")
    yield hook
    hook.run("DELETE FROM ops.readiness WHERE product = 'test.readiness'")


def test_record_readiness_is_idempotent_against_the_warehouse(warehouse):
    for status, dag_id, run_id in (
        ("running", "dag_a", "run-1"),
        ("ready", "dag_a", "run-1"),
        ("ready", "dag_b", "run-2"),
    ):
        readiness.record_readiness("test.readiness", START, END, END, run_id, status, dag_id=dag_id)
    rows = warehouse.get_records(
        "SELECT status, dag_id, run_id, watermark FROM ops.readiness "
        "WHERE product = 'test.readiness'"
    )
    assert rows == [("ready", "dag_b", "run-2", END)]


def test_readiness_state_maps_the_ledger_row(mocker):
    mocker.patch.object(PostgresHook, "get_first", return_value=("ready", END, "run-1"))
    assert readiness.readiness_state("sales.gold", START, END) == {
        "status": "ready",
        "watermark": END.isoformat(),
        "run_id": "run-1",
    }


def test_readiness_state_is_none_without_a_row(mocker):
    mocker.patch.object(PostgresHook, "get_first", return_value=None)
    assert readiness.readiness_state("sales.gold", START, END) is None


def test_file_load_sql_is_keyed_on_the_object_generation():
    sql = " ".join(readiness.FILE_LOAD_SQL.split())
    assert "ON CONFLICT (bucket, object, generation) DO UPDATE" in sql


def test_file_ledger_helpers_pass_the_generation_as_an_integer(mocker):
    run = mocker.patch.object(PostgresHook, "run")
    get_first = mocker.patch.object(PostgresHook, "get_first", return_value=("run-1",))

    readiness.record_file_load("landing", "returns/a.jsonl", "17", "partner_returns", "run-1", 3)

    assert readiness.file_already_loaded("landing", "returns/a.jsonl", "17") == "run-1"
    assert run.call_args.kwargs["parameters"]["generation"] == 17
    assert get_first.call_args.kwargs["parameters"]["generation"] == 17


@pytest.fixture
def file_ledger():
    hook = PostgresHook(postgres_conn_id="warehouse")
    try:
        hook.get_first("SELECT 1 FROM ops.file_loads LIMIT 1")
    except Exception as exc:  # noqa: BLE001 - any connectivity problem means no warehouse here
        _warehouse_unreachable("ops.file_loads", exc)
    hook.run("DELETE FROM ops.file_loads WHERE bucket = 'test-bucket'")
    yield hook
    hook.run("DELETE FROM ops.file_loads WHERE bucket = 'test-bucket'")


def test_file_ledger_is_idempotent_against_the_warehouse(file_ledger):
    assert readiness.file_already_loaded("test-bucket", "a.jsonl", 5) is None
    for run_id in ("run-1", "run-2"):
        readiness.record_file_load("test-bucket", "a.jsonl", 5, "partner_returns", run_id, 3)
    assert readiness.file_already_loaded("test-bucket", "a.jsonl", 5) == "run-2"
    assert readiness.file_already_loaded("test-bucket", "a.jsonl", 6) is None
    count = file_ledger.get_first(
        "SELECT count(*) FROM ops.file_loads WHERE bucket = 'test-bucket'"
    )
    assert count == (1,)


def test_retire_readiness_refuses_an_empty_keep():
    with pytest.raises(AirflowFailException):
        readiness.retire_readiness(["tlc.silver"], [], "run-1", dag_id="tlc_monthly")


@pytest.fixture
def monthly_ledger():
    hook = PostgresHook(postgres_conn_id="warehouse")
    try:
        hook.get_first("SELECT 1 FROM ops.readiness LIMIT 1")
    except Exception as exc:  # noqa: BLE001 - any connectivity problem means no warehouse here
        _warehouse_unreachable("warehouse", exc)
    cleanup = "DELETE FROM ops.readiness WHERE product LIKE 'test.retire.%'"
    hook.run(cleanup)
    yield hook
    hook.run(cleanup)


def test_retire_readiness_marks_months_outside_keep_once(monthly_ledger):
    months = [
        (datetime(2026, m, 1, tzinfo=UTC), datetime(2026, m + 1, 1, tzinfo=UTC)) for m in (5, 6, 7)
    ]
    for product in ("test.retire.silver", "test.retire.gold"):
        for start, end in months:
            readiness.record_readiness(product, start, end, end, "load", "ready", dag_id="tlc")
    readiness.record_readiness(
        "test.retire.other", *months[0], months[0][1], "load", "ready", dag_id="tlc"
    )
    products = ["test.retire.silver", "test.retire.gold"]

    retired = readiness.retire_readiness(products, ["2026-07", "2023-01"], "r-1", dag_id="tlc")
    again = readiness.retire_readiness(products, ["2026-07", "2023-01"], "r-2", dag_id="tlc")

    assert sorted(retired) == [
        ("test.retire.gold", "2026-05"),
        ("test.retire.gold", "2026-06"),
        ("test.retire.silver", "2026-05"),
        ("test.retire.silver", "2026-06"),
    ]
    assert again == []
    rows = monthly_ledger.get_records(
        "SELECT product, to_char(interval_start AT TIME ZONE 'UTC', 'YYYY-MM'), status, run_id"
        " FROM ops.readiness WHERE product LIKE 'test.retire.%' ORDER BY 1, 2"
    )
    assert rows == [
        ("test.retire.gold", "2026-05", "retired", "r-1"),
        ("test.retire.gold", "2026-06", "retired", "r-1"),
        ("test.retire.gold", "2026-07", "ready", "load"),
        ("test.retire.other", "2026-05", "ready", "load"),
        ("test.retire.silver", "2026-05", "retired", "r-1"),
        ("test.retire.silver", "2026-06", "retired", "r-1"),
        ("test.retire.silver", "2026-07", "ready", "load"),
    ]
