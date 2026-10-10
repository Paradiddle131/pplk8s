"""Event-triggered load of one partner returns file: exactly one scoped run per object generation.

Trigger: the event adapter (services/event-adapter) turns a GCS ``finalize`` event on
``gs://landing/returns/<YYYY-MM-DD>.jsonl`` into a run with ``conf = {bucket, object, generation}``
and the deterministic run id ``gcs__<bucket>__<object>__<generation>`` (PLAN.md D17, D18).

Flow: validate the event -> skip everything if ``ops.file_loads`` already holds that generation
-> EL Factory ``POST /load`` of exactly that generation -> dbt ``returns`` bronze, silver with an
``ops.readiness`` record after each -> ``ops.file_loads`` record last, so a generation counts as
loaded only once the whole run succeeded.

Dedupe (D18): a redelivered event gets HTTP 409 from the REST API (same run id); if the run is gone
from the metadata DB, the ledger check makes the new run a no-op.  A superseded generation (the
object was overwritten before the load) skips the rest of the run; the newer generation has its own.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from airflow.sdk import TaskGroup, dag, get_current_context, task
from pplk8s.context import file_event, safe_run_id
from pplk8s.dbt import run_dbt
from pplk8s.el_factory import ElFactoryHook
from pplk8s.readiness import file_already_loaded, record_file_load, record_readiness

PIPELINE = "returns"
ENTITY = "partner_returns"
OBJECT_PATTERN = re.compile(r"returns/(?P<day>\d{4}-\d{2}-\d{2})\.jsonl")
STAGES = ("bronze", "silver")


@dag(
    dag_id="returns_file_arrival",
    schedule=None,
    start_date=datetime(2026, 10, 1, tzinfo=UTC),
    catchup=False,
    # One file at a time: two runs would rebuild the same silver table concurrently.
    max_active_runs=1,
    tags=["events", "returns", "phase5"],
    default_args={"owner": "data-platform"},
    doc_md=__doc__,
)
def returns_file_arrival():
    @task
    def validate_event() -> dict[str, str]:
        context = get_current_context()
        event = file_event(context["dag_run"].conf, OBJECT_PATTERN)
        return {**event, "run_id": safe_run_id(context["run_id"])}

    @task.short_circuit(retries=2, retry_delay=timedelta(seconds=15))
    def not_loaded_yet(event: dict[str, str]) -> bool:
        done_by = file_already_loaded(event["bucket"], event["object"], event["generation"])
        if done_by is not None:
            print(f"generation {event['generation']} of {event['object']} loaded by {done_by}")
        return done_by is None

    @task(
        retries=3,
        retry_delay=timedelta(seconds=15),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(minutes=5),
        execution_timeout=timedelta(minutes=10),
    )
    def load(event: dict[str, str]) -> dict[str, Any]:
        return ElFactoryHook().load_file(
            ENTITY, event["bucket"], event["object"], event["generation"], event["run_id"]
        )

    def readiness_task(product: str, task_id: str):
        @task(task_id=task_id, retries=2, retry_delay=timedelta(seconds=15))
        def record(event: dict[str, str]) -> None:
            record_readiness(
                product,
                event["interval_start"],
                event["interval_end"],
                None,
                event["run_id"],
                "ready",
            )

        return record

    @task(retries=2, retry_delay=timedelta(seconds=15))
    def record_file(event: dict[str, str], summary: dict[str, Any]) -> None:
        record_file_load(
            event["bucket"],
            event["object"],
            event["generation"],
            ENTITY,
            event["run_id"],
            summary["rows"],
        )

    event = validate_event()
    summary = load(event)
    not_loaded_yet(event) >> summary

    previous = summary
    for stage in STAGES:
        with TaskGroup(group_id=f"stage_{stage}") as group:
            build = run_dbt(stage, pipeline=PIPELINE)
            build >> readiness_task(f"{PIPELINE}.{stage}", f"record_{stage}")(event)
        previous >> group
        previous = group

    previous >> record_file(event, summary)


returns_file_arrival()
