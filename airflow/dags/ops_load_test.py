"""Platform fixture (PLAN.md D24): mapped tasks that only hold a Celery worker slot for a while.

Not business logic. It loads the workers so KEDA's scale-out and scale-in can be observed, floods
pool ``ops_load`` for the slot-starvation drill, and with ``hold_mb`` holds memory on its worker for
the memory-starvation drill. Only the Phase 6 checks trigger it; it stays paused otherwise.
``retries=0`` on purpose: a task killed by a scale-in or an OOM shows up as a failure instead of
being hidden by a retry.
"""

import time

from airflow.sdk import Param, dag, get_current_context, task


@dag(
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["ops", "phase6"],
    params={
        "tasks": Param(16, type="integer", minimum=1, maximum=64),
        "seconds": Param(45, type="integer", minimum=1, maximum=600),
        "hold_mb": Param(0, type="integer", minimum=0, maximum=4096),
    },
    doc_md=__doc__,
)
def ops_load_test():
    @task
    def plan() -> list[int]:
        params = get_current_context()["params"]
        return [params["seconds"]] * params["tasks"]

    @task(pool="ops_load", retries=0)
    def hold_slot(seconds: int) -> None:
        mb = get_current_context()["params"]["hold_mb"]
        held = [bytearray(1024 * 1024) for _ in range(mb)]  # noqa: F841 - held until the task ends
        time.sleep(seconds)

    hold_slot.expand(seconds=plan())


ops_load_test()
