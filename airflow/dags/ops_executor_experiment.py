"""Platform experiment (PLAN.md D25): the same trivial task on the Celery and Kubernetes executors.

Not business logic. It measures what a per-task pod costs and buys: queued-to-running latency,
where the task ran, and memory isolation (``exceed_memory`` allocates past its own pod's limit and
should be OOMKilled alone). Results are written up in docs/executors.md.

The DAG exists only while values-multi-executor.yaml configures KubernetesExecutor next to Celery:
a task naming an executor the deployment lacks is an import error (UnknownExecutorException).
"""

import logging
import socket

from airflow.sdk import Param, conf, dag, get_current_context, task
from kubernetes.client import models as k8s

log = logging.getLogger(__name__)
EXECUTORS = {name.strip().rsplit(".", 1)[-1] for name in conf.get("core", "executor").split(",")}

# A small pod for the isolation probe, so exceeding it never touches a Celery worker's memory.
SMALL_POD = {
    "pod_override": k8s.V1Pod(
        spec=k8s.V1PodSpec(
            containers=[
                k8s.V1Container(
                    name="base",
                    resources=k8s.V1ResourceRequirements(
                        requests={"memory": "256Mi"}, limits={"memory": "384Mi"}
                    ),
                )
            ]
        )
    )
}

if "KubernetesExecutor" in EXECUTORS:

    @dag(
        schedule=None,
        catchup=False,
        tags=["ops", "phase6"],
        params={"exceed_mb": Param(0, type="integer", minimum=0, maximum=2048)},
        doc_md=__doc__,
    )
    def ops_executor_experiment():
        @task
        def on_celery() -> str:
            return socket.gethostname()

        @task(executor="KubernetesExecutor")
        def on_kubernetes() -> str:
            return socket.gethostname()

        @task(executor="KubernetesExecutor", executor_config=SMALL_POD, retries=0)
        def exceed_memory() -> int:
            """Hold ``exceed_mb`` MiB in this task's own pod (0 skips the probe)."""
            mb = get_current_context()["params"]["exceed_mb"]
            held = [bytearray(1024 * 1024) for _ in range(mb)]
            log.info("held %d MiB on %s", len(held), socket.gethostname())
            return len(held)

        on_celery()
        on_kubernetes()
        exceed_memory()

    ops_executor_experiment()
