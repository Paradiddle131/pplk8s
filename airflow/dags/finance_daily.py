"""Daily finance view that depends on two other pipelines through the readiness ledger.

Waits (deferrable, in the triggerer, holding no worker slot) until ``sales.gold`` and
``returns.silver`` are ``ready`` in ``ops.readiness`` for the run's interval, then builds the
``finance`` exposed models and records ``finance.exposed`` (PLAN.md D19).

The producers are ``sales_elt`` (scheduled) and ``returns_file_arrival`` (event-triggered); this DAG
knows only their ledger products, never their DAG ids, so either could move to another Airflow or
another tool without changing it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from airflow.sdk import dag, get_current_context, task
from pplk8s.context import run_interval, safe_run_id
from pplk8s.dbt import run_dbt
from pplk8s.readiness import record_readiness
from pplk8s.sensors import ReadinessSensor

PIPELINE = "finance"
UPSTREAM = ("sales.gold", "returns.silver")


@dag(
    dag_id="finance_daily",
    schedule="@daily",
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,
    # Waiting runs are deferred and cost no worker slot, so one interval waiting for its producers
    # must not block another; only the dbt build is serialised across runs (below).
    max_active_runs=4,
    tags=["finance", "phase5"],
    default_args={"owner": "data-platform"},
    doc_md=__doc__,
)
def finance_daily():
    # Even the first task gets a retry budget: a transient blip here would fail the whole run.
    @task(multiple_outputs=True, retries=2, retry_delay=timedelta(seconds=15))
    def resolve_context() -> dict[str, str]:
        context = get_current_context()
        start, end = run_interval(context)
        return {
            "run_id": safe_run_id(context["run_id"]),
            "interval_start": start.isoformat(),
            "interval_end": end.isoformat(),
        }

    @task(retries=2, retry_delay=timedelta(seconds=15))
    def record(ctx: dict[str, str], sales: dict[str, str]) -> None:
        record_readiness(
            f"{PIPELINE}.exposed",
            ctx["interval_start"],
            ctx["interval_end"],
            sales["watermark"],
            ctx["run_id"],
            "ready",
        )

    ctx = resolve_context()
    waits = {
        product: ReadinessSensor(
            task_id=f"wait_{product.replace('.', '_')}",
            product=product,
            interval_start=ctx["interval_start"],
            interval_end=ctx["interval_end"],
            poll_interval=15,
            timeout=timedelta(hours=6),
        )
        for product in UPSTREAM
    }
    # Two runs rebuilding the same views at once would race; one build at a time across runs.
    build = run_dbt("exposed", pipeline=PIPELINE, max_active_tis_per_dag=1)
    list(waits.values()) >> build
    build >> record(ctx, waits["sales.gold"].output)


finance_daily()
