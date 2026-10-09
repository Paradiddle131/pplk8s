"""``run_dbt``: the dbt task factory of the workload seam (PLAN.md D7).

Today a stage runs as a ``KubernetesPodOperator`` pod from the dbt image (the Cloud Run Job
stand-in).  Every Kubernetes detail lives in this module, so moving to Cloud Composer means
returning a ``CloudRunExecuteJobOperator`` from :func:`run_dbt` and nothing else changes.

Retry ownership (PLAN.md D15): Airflow task retries are the only retry layer for dbt.
A failed or evicted pod fails the task, and the retry runs the same
``dbt build --select <stage>`` again from scratch in a fresh pod.
``dbt retry`` is deliberately not used: it resumes from ``target/run_results.json`` of the
previous invocation, and that artifact dies with the ephemeral pod (a Cloud Run Job execution
has the same property), so a retry would find nothing to resume from.
Re-running the whole stage is safe because dbt builds are idempotent (tables and views are
rebuilt, tests re-run).

Overrides (resolved at task run time, so the DAG parse never reads the metadata DB):
Airflow Variables ``dbt_image`` and ``dbt_namespace``; defaults below.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

STAGES = ("bronze", "silver", "gold", "exposed")
DEFAULT_IMAGE = "localhost:5001/dbt:0.1.0"
DEFAULT_NAMESPACE = "workloads"
SERVICE_ACCOUNT = "dbt"
CREDENTIALS_SECRET = "warehouse-credentials"
RUN_AS_ID = 10001
SCRATCH = {"target": "/dbt/target", "logs": "/dbt/logs", "tmp": "/tmp"}  # noqa: S108

_IMAGE = f"{{{{ var.value.get('dbt_image', '{DEFAULT_IMAGE}') }}}}"
_NAMESPACE = f"{{{{ var.value.get('dbt_namespace', '{DEFAULT_NAMESPACE}') }}}}"


def run_dbt(stage: str, *, task_id: str | None = None, **kwargs: Any) -> KubernetesPodOperator:
    """Return the operator that runs ``dbt build --select <stage>``.

    ``kwargs`` override any operator argument (retries, execution_timeout, pool, ...).
    """
    if stage not in STAGES:
        raise ValueError(f"unknown dbt stage {stage!r}; expected one of {STAGES}")
    options: dict[str, Any] = {
        "task_id": task_id or f"dbt_{stage}",
        "name": f"dbt-{stage}",  # KPO appends a random suffix, so concurrent runs never collide
        "namespace": _NAMESPACE,
        "image": _IMAGE,
        "arguments": ["build", "--select", stage],
        "service_account_name": SERVICE_ACCOUNT,
        "env_from": [
            k8s.V1EnvFromSource(secret_ref=k8s.V1SecretEnvSource(name=CREDENTIALS_SECRET))
        ],
        "container_resources": k8s.V1ResourceRequirements(
            requests={"cpu": "100m", "memory": "256Mi"},
            limits={"cpu": "500m", "memory": "512Mi"},
        ),
        # Pod security: comply with the `restricted` profile of the workloads namespace
        # (same settings as platform/k8s/dbt-job.template.yaml).
        "automount_service_account_token": False,
        "security_context": k8s.V1PodSecurityContext(
            run_as_non_root=True,
            run_as_user=RUN_AS_ID,
            run_as_group=RUN_AS_ID,
            seccomp_profile=k8s.V1SeccompProfile(type="RuntimeDefault"),
        ),
        "container_security_context": k8s.V1SecurityContext(
            allow_privilege_escalation=False,
            read_only_root_filesystem=True,
            capabilities=k8s.V1Capabilities(drop=["ALL"]),
        ),
        # dbt writes compiled SQL, run results and logs; give it scratch space on a read-only root.
        "volumes": [k8s.V1Volume(name=n, empty_dir=k8s.V1EmptyDirVolumeSource()) for n in SCRATCH],
        "volume_mounts": [k8s.V1VolumeMount(name=n, mount_path=p) for n, p in SCRATCH.items()],
        "on_finish_action": "delete_pod",
        "get_logs": True,
        "log_events_on_failure": True,
        "startup_timeout_seconds": 300,
        "labels": {"app.kubernetes.io/name": "dbt", "pplk8s/stage": stage},
        "retries": 2,
        "retry_delay": timedelta(seconds=30),
        "retry_exponential_backoff": True,
        "max_retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=30),
    }
    options.update(kwargs)
    return KubernetesPodOperator(**options)
