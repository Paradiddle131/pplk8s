from datetime import UTC, datetime

import pytest
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk.exceptions import AirflowFailException
from pplk8s import readiness

START = datetime(2026, 10, 8, tzinfo=UTC)
END = datetime(2026, 10, 9, tzinfo=UTC)


def test_upsert_sql_is_keyed_on_the_ledger_primary_key():
    sql = " ".join(readiness.UPSERT_SQL.split())
    assert "ON CONFLICT (product, interval_start, interval_end) DO UPDATE" in sql
    assert "updated_at = now()" in sql


def test_record_readiness_passes_parameters(mocker):
    run = mocker.patch.object(PostgresHook, "run")
    readiness.record_readiness("sales.gold", START, END, END, "run-1", "ready")
    run.assert_called_once()
    assert run.call_args.args[0] == readiness.UPSERT_SQL
    assert run.call_args.kwargs["parameters"] == {
        "product": "sales.gold",
        "interval_start": START,
        "interval_end": END,
        "watermark": END,
        "run_id": "run-1",
        "status": "ready",
    }


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
        pytest.skip(f"warehouse not reachable at localhost:5433 (make services-up): {exc}")
    hook.run("DELETE FROM ops.readiness WHERE product = 'test.readiness'")
    yield hook
    hook.run("DELETE FROM ops.readiness WHERE product = 'test.readiness'")


def test_record_readiness_is_idempotent_against_the_warehouse(warehouse):
    for status, run_id in (("running", "run-1"), ("ready", "run-1"), ("ready", "run-2")):
        readiness.record_readiness("test.readiness", START, END, END, run_id, status)
    rows = warehouse.get_records(
        "SELECT status, run_id, watermark FROM ops.readiness WHERE product = 'test.readiness'"
    )
    assert rows == [("ready", "run-2", END)]
