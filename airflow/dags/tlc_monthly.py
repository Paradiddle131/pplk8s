"""Monthly NYC TLC trips: publication wait, EL Factory file extraction, dbt month by month.

Flow: resolve the data month -> catalog -> one deferrable publication wait per catalog entry ->
one mapped extract per entry (pool ``el_factory``) -> dbt bronze, silver, gold, exposed for that
month, with an ``ops.readiness`` row ``tlc.<stage>`` after each stage.

Schedule (PLAN.md D35): monthly with an explicit ``CronDataIntervalTimetable``, so a run's data
interval is the data month it loads and its logical date names that month. The plain ``@monthly``
string would give Airflow 3's ``CronTriggerTimetable`` (``create_cron_data_intervals = False``):
an empty interval at the fire time, and a logical date in the month after the data.
``catchup=True`` from ``START`` heals month boundaries that passed while the lab was off;
older months come only through Airflow's backfill
(``airflow backfill create``). ``max_active_runs=3`` lets the 1-3 months of publication lag wait
side by side: each run waits deferrably (no worker slot) for up to 120 days, and the wait timing
out fails the run, which is the missing-month alert.

Airflow orchestrates only: EL Factory streams the month's file into ``ds_source`` chunk by chunk
and resumes a retry from its chunk ledger (D34); dbt replaces the month in each layer (D36).
XCom carries identifiers and compact summaries, never data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from airflow.sdk import CronDataIntervalTimetable, TaskGroup, dag, get_current_context, task
from pplk8s.context import run_month, safe_run_id
from pplk8s.dbt import STAGES, run_dbt
from pplk8s.el_factory import ElFactoryHook
from pplk8s.readiness import record_readiness
from pplk8s.sensors import PublicationSensor

PIPELINE = "tlc"
EXTRACT_POOL = "el_factory"
# The first scheduled month: the latest three published when the DAG was added (2026-10, D35).
START = datetime(2026, 6, 1, tzinfo=UTC)

# Per-entity time budget for one extract attempt (D34). A yellow month is 3-5 chunks of ~18 MB
# (measured: 25-50 s), green one ~1 MB chunk, FHVHV ~20 chunks of ~26 MB (drill only, D35).
# A mapped task has a single execution_timeout, so the hook enforces each entity's budget between
# requests and EXTRACT_TIMEOUT is only the hard stop above the largest budget.
EXTRACT_BUDGETS = {
    "yellow": timedelta(minutes=20),
    "green": timedelta(minutes=5),
    "fhvhv": timedelta(minutes=60),
}
DEFAULT_BUDGET = timedelta(minutes=30)
EXTRACT_TIMEOUT = max([*EXTRACT_BUDGETS.values(), DEFAULT_BUDGET]) + timedelta(minutes=5)

# dbt builds exactly the run's data month (D36); rendered when each dbt task runs.
DATA_MONTH = "{{ ti.xcom_pull(task_ids='resolve_context')['data_month'] }}"


@dag(
    dag_id="tlc_monthly",
    schedule=CronDataIntervalTimetable("0 0 1 * *", timezone="UTC"),
    start_date=START,
    catchup=True,
    max_active_runs=3,
    tags=["elt", "tlc", "phase8"],
    default_args={"owner": "data-platform"},
    doc_md=__doc__,
)
def tlc_monthly():
    @task(retries=2, retry_delay=timedelta(seconds=15))
    def resolve_context() -> dict[str, str]:
        context = get_current_context()
        start, end, month = run_month(context)
        return {
            "run_id": safe_run_id(context["run_id"]),
            "interval_start": start.isoformat(),
            "interval_end": end.isoformat(),
            "data_month": month,
        }

    @task(
        retries=3,
        retry_delay=timedelta(seconds=15),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=5),
        execution_timeout=timedelta(minutes=10),
    )
    def get_catalog() -> list[dict[str, str]]:
        return ElFactoryHook().get_catalog(PIPELINE)

    @task(retries=2, retry_delay=timedelta(seconds=15))
    def publication_targets(
        catalog: list[dict[str, str]], ctx: dict[str, str]
    ) -> list[dict[str, str]]:
        return [
            {"source": e["source"], "entity": e["entity"], "month": ctx["data_month"]}
            for e in catalog
        ]

    @task(
        pool=EXTRACT_POOL,
        retries=3,
        retry_delay=timedelta(seconds=30),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=5),
        execution_timeout=EXTRACT_TIMEOUT,
        map_index_template="{{ entry_label }}",
    )
    def extract(entry: dict[str, str], ctx: dict[str, str]) -> dict[str, Any]:
        get_current_context()["entry_label"] = f"{entry['source']}.{entry['entity']}"
        budget = EXTRACT_BUDGETS.get(entry["entity"], DEFAULT_BUDGET)
        return ElFactoryHook().extract_entity(
            entry["source"],
            entry["entity"],
            ctx["run_id"],
            ctx["interval_start"],
            ctx["interval_end"],
            budget_seconds=budget.total_seconds(),
        )

    def readiness_task(product: str, task_id: str):
        @task(
            task_id=task_id,
            retries=2,
            retry_delay=timedelta(seconds=15),
            execution_timeout=timedelta(minutes=2),
        )
        def record(ctx: dict[str, str]) -> None:
            # The watermark of a month is its end (D36): every trip of the month is in.
            record_readiness(
                product,
                ctx["interval_start"],
                ctx["interval_end"],
                ctx["interval_end"],
                ctx["run_id"],
                "ready",
                dag_id=get_current_context()["dag"].dag_id,
            )

        return record

    ctx = resolve_context()
    catalog = get_catalog()
    published = PublicationSensor.partial(
        task_id="wait_published",
        retries=2,
        retry_delay=timedelta(minutes=1),
        map_index_template="{{ task.source }}.{{ task.entity }}",
    ).expand_kwargs(publication_targets(catalog, ctx))
    summaries = extract.partial(ctx=ctx).expand(entry=catalog)
    published >> summaries

    previous = summaries
    for stage in STAGES:
        with TaskGroup(group_id=f"stage_{stage}") as group:
            build = run_dbt(stage, pipeline=PIPELINE, vars={"data_month": DATA_MONTH})
            record = readiness_task(f"{PIPELINE}.{stage}", f"record_{stage}")(ctx)
            build >> record
        previous >> group
        previous = group


tlc_monthly()
