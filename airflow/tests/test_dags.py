from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from airflow.dag_processing.dagbag import DagBag

DAGS = Path(__file__).resolve().parents[1] / "dags"


@pytest.fixture(scope="module")
def bag():
    return DagBag(dag_folder=str(DAGS))


def test_no_import_errors(bag):
    assert bag.import_errors == {}


def test_synced_folder_parses_only_dags(bag):
    """git-sync serves all of airflow/ as the DAG folder (PLAN.md D23); .airflowignore must keep
    include/ and tests/ away from the DAG processor, so it finds exactly the DAGs in dags/."""
    synced = DagBag(dag_folder=str(DAGS.parent))
    assert synced.import_errors == {}
    assert set(synced.dag_ids) == set(bag.dag_ids)
    assert {Path(dag.fileloc).parent for dag in synced.dags.values()} == {DAGS}


def test_hello_structure(bag):
    hello = bag.dags["hello"]
    assert hello.catchup is False
    assert hello.schedule is None
    assert list(hello.task_ids) == ["say_hello"]


@pytest.fixture(scope="module", params=["sales", "marketing", "call_transcripts"])
def elt(request, bag):
    """The ELT DAGs the shared builder makes (PLAN.md D38): (pipeline, DAG)."""
    return request.param, bag.dags[f"{request.param}_elt"]


def test_elt_dag_settings(elt):
    pipeline, sales = elt
    assert sales.catchup is False
    assert sales.max_active_runs == 1
    assert pipeline in sales.tags
    assert str(sales.schedule) in ("@daily", "0 0 * * *") or "daily" in str(sales.timetable).lower()


def test_elt_task_ids(elt):
    pipeline, sales = elt
    ids = set(sales.task_ids)
    assert {
        "resolve_context",
        "get_catalog",
        "extract",
        "check_extracted",
        f"record_{pipeline}",
    } <= ids
    for stage in ("bronze", "silver", "gold", "exposed"):
        assert f"stage_{stage}.dbt_{stage}" in ids
        assert f"stage_{stage}.record_{stage}" in ids


def test_extract_is_mapped_in_pool_with_retries(elt):
    _, sales = elt
    extract = sales.get_task("extract")
    assert extract.is_mapped
    assert extract.partial_kwargs["pool"] == "el_factory"
    assert extract.partial_kwargs["retries"] == 3
    assert extract.partial_kwargs["retry_exponential_backoff"] is True
    assert extract.partial_kwargs["execution_timeout"] == timedelta(minutes=15)


def test_stage_order(elt):
    pipeline, sales = elt
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
        f"record_{pipeline}",
    ]
    for upstream, downstream in zip(chain, chain[1:], strict=False):
        assert downstream in sales.get_task(upstream).downstream_task_ids, (upstream, downstream)
    assert "extract" in sales.get_task("check_extracted").upstream_task_ids


def test_dbt_tasks_use_retries_and_timeouts(elt):
    _, sales = elt
    for stage in ("bronze", "silver", "gold", "exposed"):
        task = sales.get_task(f"stage_{stage}.dbt_{stage}")
        assert task.retries >= 1
        assert task.execution_timeout is not None


def test_every_elt_call_to_el_factory_is_retried(elt):
    _, sales = elt
    for task_id in ("get_catalog", "check_extracted"):
        task = sales.get_task(task_id)
        assert task.retries >= 2, task_id
        assert task.execution_timeout is not None, task_id
    assert sales.get_task("get_catalog").retry_exponential_backoff is True


@pytest.fixture(scope="module")
def tlc(bag):
    return bag.dags["tlc_monthly"]


def test_tlc_runs_monthly_with_catchup_and_three_months_in_flight(tlc):
    # A data-interval timetable: the first run's interval is the first data month, and its
    # logical date names it (D35); a trigger timetable would load May in a run dated June.
    # The SDK class only declares the schedule; the scheduler's core class computes the runs.
    from airflow.timetables.base import TimeRestriction
    from airflow.timetables.interval import CronDataIntervalTimetable

    assert type(tlc.timetable).__name__ == "CronDataIntervalTimetable"
    scheduler_side = CronDataIntervalTimetable(tlc.timetable.expression, tlc.timetable.timezone)
    first = scheduler_side.next_dagrun_info(
        last_automated_data_interval=None,
        restriction=TimeRestriction(tlc.start_date, None, catchup=True),
    )
    june = (datetime(2026, 6, 1, tzinfo=UTC), datetime(2026, 7, 1, tzinfo=UTC))
    assert (first.data_interval.start, first.data_interval.end) == june
    assert tlc.catchup is True
    assert tlc.max_active_runs == 3
    assert tlc.start_date.day == 1


def test_tlc_waits_for_publication_retires_then_extracts_and_builds_each_stage(tlc):
    from pplk8s.sensors import PublicationSensor

    wait = tlc.get_task("wait_published")
    assert wait.is_mapped
    assert wait.operator_class.__name__ == PublicationSensor.__name__
    chain = [
        "wait_published",
        "retire.plan",
        "retire.landing",
        "retire.dbt",
        "retire.readiness",
        "extract",
        "stage_bronze.dbt_bronze",
        "stage_bronze.record_bronze",
        "stage_silver.dbt_silver",
        "stage_silver.record_silver",
        "stage_gold.dbt_gold",
        "stage_gold.record_gold",
        "stage_exposed.dbt_exposed",
        "stage_exposed.record_exposed",
    ]
    for upstream, downstream in zip(chain, chain[1:], strict=False):
        assert downstream in tlc.get_task(upstream).downstream_task_ids, (upstream, downstream)


def test_tlc_extract_is_mapped_in_the_el_factory_pool_with_a_hard_timeout(tlc):
    from tlc_monthly import EXTRACT_BUDGETS

    extract = tlc.get_task("extract")
    assert extract.is_mapped
    assert extract.partial_kwargs["pool"] == "el_factory"
    assert extract.partial_kwargs["retries"] >= 1
    assert extract.partial_kwargs["execution_timeout"] > max(EXTRACT_BUDGETS.values())


def test_tlc_dbt_stages_build_only_tlc_models_of_the_run_month(tlc):
    for stage in ("bronze", "silver", "gold", "exposed"):
        task = tlc.get_task(f"stage_{stage}.dbt_{stage}")
        assert task.arguments[:3] == ["build", "--select", f"tag:tlc,tag:{stage}"]
        assert task.arguments[3] == "--vars"
        assert "resolve_context" in task.arguments[4] and "data_month" in task.arguments[4]


def test_tlc_retires_the_months_outside_d35_before_loading(tlc):
    # Retention mirrors partition expiration, before the load (D35, #87): landing per catalog
    # entry, then dbt's own tables with the planned keep list, then the readiness rows.
    from tlc_monthly import DRIFT_MONTHS, LATEST_MONTHS, START

    assert tlc.get_task("retire.landing").is_mapped
    dbt = tlc.get_task("retire.dbt")
    assert dbt.arguments[:3] == ["run-operation", "tlc_retire", "--args"]
    assert "retire.plan" in dbt.arguments[3] and "keep" in dbt.arguments[3]
    assert "join(',')" in dbt.arguments[3]
    assert (START.strftime("%Y-%m"), LATEST_MONTHS) == ("2026-06", 3)
    assert DRIFT_MONTHS == ("2023-01", "2025-01", "2026-06")


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


def test_finance_validates_the_semantic_layer_after_exposed_beside_its_record(finance):
    validate = finance.get_task("validate_semantic_layer")
    assert validate.upstream_task_ids == {"dbt_exposed"}
    # Only the semantic models of the pipelines it waited for are queried on the warehouse (#168).
    assert validate.arguments[-1].endswith("validate_semantic.py --pipelines returns,sales")
    # A broken semantic layer fails the run but never holds back finance.exposed.
    assert "validate_semantic_layer" not in finance.get_task("record").upstream_task_ids


def test_finance_runs_wait_in_parallel_but_build_one_at_a_time(finance):
    assert finance.max_active_runs > 1
    assert finance.get_task("dbt_exposed").max_active_tis_per_dag == 1


def test_elt_dbt_stages_select_only_their_pipelines_models(elt):
    pipeline, dag = elt
    for stage in ("bronze", "silver", "gold", "exposed"):
        task = dag.get_task(f"stage_{stage}.dbt_{stage}")
        assert task.arguments[-1] == f"tag:{pipeline},tag:{stage}"


@pytest.mark.parametrize(
    "dag_id",
    [
        "sales_elt",
        "marketing_elt",
        "call_transcripts_elt",
        "returns_file_arrival",
        "finance_daily",
        "tlc_monthly",
    ],
)
def test_every_business_task_survives_a_lost_worker(bag, dag_id):
    """KEDA scale-in, a drain, or an OOM can kill a running task; Celery's warm shutdown only waits
    terminationGracePeriodSeconds (PLAN.md D24). The scheduler fails the orphan after the heartbeat
    timeout, so only a retry keeps the run alive. Bad input still fails fast
    (AirflowFailException)."""
    dag = bag.dags[dag_id]
    for task in dag.tasks:
        retries = task.partial_kwargs["retries"] if task.is_mapped else task.retries
        assert retries >= 1, f"{dag_id}.{task.task_id} has no retries"


def test_ops_load_test_holds_slots_in_its_own_pool(bag):
    load = bag.dags["ops_load_test"]
    hold = load.get_task("hold_slot")
    assert hold.pool == "ops_load"
    assert hold.retries == 0
    assert load.schedule is None


def test_executor_experiment_exists_only_with_kubernetes_executor(bag, monkeypatch):
    # Without KubernetesExecutor configured the DAG must not exist: naming an unavailable executor
    # is an import error on the DAG processor.
    assert "ops_executor_experiment" not in bag.dags
    monkeypatch.setenv("AIRFLOW__CORE__EXECUTOR", "CeleryExecutor,KubernetesExecutor")
    multi = DagBag(dag_folder=str(DAGS / "ops_executor_experiment.py"))
    assert multi.import_errors == {}
    dag = multi.dags["ops_executor_experiment"]
    assert dag.get_task("on_kubernetes").executor == "KubernetesExecutor"
    assert dag.get_task("on_celery").executor is None
