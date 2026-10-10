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


def test_hello_structure(bag):
    hello = bag.dags["hello"]
    assert hello.catchup is False
    assert hello.schedule is None
    assert list(hello.task_ids) == ["say_hello"]


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


def test_every_elt_call_to_el_factory_is_retried(sales):
    for task_id in ("get_catalog", "check_extracted"):
        task = sales.get_task(task_id)
        assert task.retries >= 2, task_id
        assert task.execution_timeout is not None, task_id
    assert sales.get_task("get_catalog").retry_exponential_backoff is True


@pytest.fixture(scope="module")
def returns(bag):
    return bag.dags["returns_file_arrival"]


def test_returns_dag_is_event_triggered_and_serial(returns):
    assert returns.schedule is None
    assert returns.catchup is False
    assert returns.max_active_runs == 1


def test_returns_flow_checks_the_ledger_before_loading_and_records_it_last(returns):
    order = [
        "validate_event",
        "not_loaded_yet",
        "load",
        "stage_bronze.dbt_bronze",
        "stage_bronze.record_bronze",
        "stage_silver.dbt_silver",
        "stage_silver.record_silver",
        "record_file",
    ]
    for upstream, downstream in zip(order, order[1:], strict=False):
        ancestors = returns.get_task(downstream).get_flat_relative_ids(upstream=True)
        assert upstream in ancestors, f"{upstream} must run before {downstream}"
    assert returns.get_task("stage_silver.dbt_silver").arguments[-1] == "tag:returns,tag:silver"


@pytest.fixture(scope="module")
def finance(bag):
    return bag.dags["finance_daily"]


def test_finance_waits_deferrably_on_both_producers_before_building(finance):
    build = finance.get_task("dbt_exposed")
    assert build.arguments[-1] == "tag:finance,tag:exposed"
    for product, task_id in (
        ("sales.gold", "wait_sales_gold"),
        ("returns.silver", "wait_returns_silver"),
    ):
        wait = finance.get_task(task_id)
        assert wait.product == product
        assert wait.deferrable is True
        assert task_id in build.upstream_task_ids
    assert "dbt_exposed" in finance.get_task("record").upstream_task_ids


def test_finance_runs_wait_in_parallel_but_build_one_at_a_time(finance):
    assert finance.max_active_runs > 1
    assert finance.get_task("dbt_exposed").max_active_tis_per_dag == 1


def test_sales_dbt_stages_select_only_sales_models(sales):
    for stage in ("bronze", "silver", "gold", "exposed"):
        assert (
            sales.get_task(f"stage_{stage}.dbt_{stage}").arguments[-1] == f"tag:sales,tag:{stage}"
        )
