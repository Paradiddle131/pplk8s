"""Scheduled sales ELT: EL Factory extraction, readiness check, dbt medallion build.

Flow: resolve run context -> catalog -> one mapped extract task per catalog entry (pool
``el_factory``) -> extraction check and watermark -> dbt bronze, silver, gold, exposed with an
``ops.readiness`` record after each stage -> final ``sales`` record.

Airflow orchestrates only: EL Factory extracts and loads, dbt transforms.
XCom carries identifiers, timestamps and compact summaries, never data.
Retries (PLAN.md D15): Airflow task retries own every transient fault; see ``pplk8s.el_factory``
and ``pplk8s.dbt`` for how EL Factory and dbt cooperate with that.

dbt (PLAN.md D20): each stage builds only the models tagged ``sales`` and the stage's layer.

Readiness products: one per stage (``sales.bronze`` ... ``sales.exposed``) so a consumer can wait
for exactly the layer it reads, plus ``sales`` once the whole run is done.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from airflow.sdk import TaskGroup, dag, get_current_context, task
from pplk8s.context import run_interval, safe_run_id
from pplk8s.dbt import STAGES, run_dbt
from pplk8s.el_factory import ElFactoryHook
from pplk8s.readiness import check_extraction, record_readiness

PIPELINE = "sales"
EXTRACT_POOL = "el_factory"


@dag(
    dag_id="sales_elt",
    schedule="@daily",
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    tags=["elt", "sales", "phase4"],
    default_args={"owner": "data-platform"},
    doc_md=__doc__,
)
def sales_elt():
    # Even the first task gets a retry budget: a transient blip here would fail the whole run.
    @task(retries=2, retry_delay=timedelta(seconds=15))
    def resolve_context() -> dict[str, str]:
        context = get_current_context()
        start, end = run_interval(context)
        return {
            "run_id": safe_run_id(context["run_id"]),
            "interval_start": start.isoformat(),
            "interval_end": end.isoformat(),
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

    @task(
        pool=EXTRACT_POOL,
        retries=3,
        retry_delay=timedelta(seconds=15),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=5),
        execution_timeout=timedelta(minutes=15),
        map_index_template="{{ entry_label }}",
    )
    def extract(entry: dict[str, str], ctx: dict[str, str]) -> dict[str, Any]:
        get_current_context()["entry_label"] = f"{entry['source']}.{entry['entity']}"
        return ElFactoryHook().extract_entity(
            entry["source"],
            entry["entity"],
            ctx["run_id"],
            ctx["interval_start"],
            ctx["interval_end"],
        )

    @task(retries=2, retry_delay=timedelta(seconds=30), execution_timeout=timedelta(minutes=5))
    def check_extracted(summaries: list[dict[str, Any]], ctx: dict[str, str]) -> dict[str, Any]:
        return check_extraction(
            summaries, ctx["run_id"], ctx["interval_start"], ctx["interval_end"]
        )

    def readiness_task(product: str, task_id: str):
        @task(
            task_id=task_id,
            retries=2,
            retry_delay=timedelta(seconds=15),
            execution_timeout=timedelta(minutes=2),
        )
        def record(ctx: dict[str, str], check: dict[str, Any]) -> None:
            record_readiness(
                product,
                ctx["interval_start"],
                ctx["interval_end"],
                check["watermark"],
                ctx["run_id"],
                "ready",
                dag_id=get_current_context()["dag"].dag_id,
            )

        return record

    ctx = resolve_context()
    summaries = extract.partial(ctx=ctx).expand(entry=get_catalog())
    check = check_extracted(summaries, ctx)

    previous = check
    for stage in STAGES:
        with TaskGroup(group_id=f"stage_{stage}") as group:
            build = run_dbt(stage, pipeline=PIPELINE)
            record = readiness_task(f"{PIPELINE}.{stage}", f"record_{stage}")(ctx, check)
            build >> record
        previous >> group
        previous = group

    final = readiness_task(PIPELINE, "record_sales")(ctx, check)
    previous >> final


sales_elt()
