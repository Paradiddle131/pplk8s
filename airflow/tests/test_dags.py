from datetime import timedelta
from pathlib import Path

import pytest
from airflow.dag_processing.dagbag import DagBag

DAGS = Path(__file__).resolve().parents[1] / "dags"


@pytest.fixture(scope="module")
def bag():
    return DagBag(dag_folder=str(DAGS))


def test_no_import_errors(bag):
    assert bag.import_errors == {}


def test_hello_dag_loads_when_present(bag):
    if not (DAGS / "hello.py").exists():
        pytest.skip("hello.py is delivered by Phase 3")
    assert bag.dags


@pytest.fixture(scope="module")
def sales(bag):
    return bag.dags["sales_elt"]


def test_sales_dag_settings(sales):
    assert sales.catchup is False
    assert sales.max_active_runs == 1
    assert "sales" in sales.tags
    assert str(sales.schedule) in ("@daily", "0 0 * * *") or "daily" in str(sales.timetable).lower()


def test_sales_task_ids(sales):
    ids = set(sales.task_ids)
    assert {"resolve_context", "get_catalog", "extract", "check_extracted", "record_sales"} <= ids
    for stage in ("bronze", "silver", "gold", "exposed"):
        assert f"stage_{stage}.dbt_{stage}" in ids
        assert f"stage_{stage}.record_{stage}" in ids


def test_extract_is_mapped_in_pool_with_retries(sales):
    extract = sales.get_task("extract")
    assert extract.is_mapped
    assert extract.partial_kwargs["pool"] == "el_factory"
    assert extract.partial_kwargs["retries"] == 3
    assert extract.partial_kwargs["retry_exponential_backoff"] is True
    assert extract.partial_kwargs["execution_timeout"] == timedelta(minutes=15)


def test_stage_order(sales):
    chain = [
        "check_extracted",
        "stage_bronze.dbt_bronze",
        "stage_bronze.record_bronze",
        "stage_silver.dbt_silver",
        "stage_silver.record_silver",
        "stage_gold.dbt_gold",
        "stage_gold.record_gold",
        "stage_exposed.dbt_exposed",
        "stage_exposed.record_exposed",
        "record_sales",
    ]
    for upstream, downstream in zip(chain, chain[1:], strict=False):
        assert downstream in sales.get_task(upstream).downstream_task_ids, (upstream, downstream)
    assert "extract" in sales.get_task("check_extracted").upstream_task_ids


def test_dbt_tasks_use_retries_and_timeouts(sales):
    for stage in ("bronze", "silver", "gold", "exposed"):
        task = sales.get_task(f"stage_{stage}.dbt_{stage}")
        assert task.retries >= 1
        assert task.execution_timeout is not None
