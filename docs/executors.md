# Celery vs KubernetesExecutor

Phase 6 experiment (PLAN.md D5, D25).
Celery stays the only executor of the default deployment; this page records what running a task in a pod of its own costs and buys, measured on the lab.

## How it was run

- Overlay `platform/helm/airflow/values-multi-executor.yaml` sets `executor: "CeleryExecutor,KubernetesExecutor"`; Celery, listed first, stays the default.
- DAG `ops_executor_experiment` runs the same trivial task twice, once on Celery (`on_celery`) and once with `executor="KubernetesExecutor"` (`on_kubernetes`), plus `exceed_memory`, which holds `exceed_mb` MiB inside its own pod limited to 384Mi.
- `tests/e2e/executor-experiment.sh` triggers it, reads the task instances through the REST API, and checks log availability and memory isolation.

```bash
make airflow-up AIRFLOW_OVERLAYS=values-multi-executor.yaml
tests/e2e/executor-experiment.sh
make airflow-up   # back to Celery only
```

## Measurements (2026-10-10, kind on WSL2, images cached on the nodes)

| | Celery worker | KubernetesExecutor pod |
|---|---|---|
| Queued → running (3 runs) | 0 s, 0 s, 1 s | 2 s, 5 s, 5 s |
| Task duration as recorded (trivial task) | 0.08 s (2.3 s on the first run after a worker start) | 1.4–1.5 s, every run |
| Where it ran | a long-lived worker pod (one IP for all runs) | a new pod per task (a new IP every run) |
| Log after the pod is gone | from `gs://airflow-logs` | from `gs://airflow-logs` once the task ended normally |
| Log of a task killed by the kernel (OOM) | n/a in this experiment | **lost**: the pod died before uploading; the API answers `Could not read served logs … timed out` |
| Memory isolation | tasks share the worker container's limit | `exceed_memory` was `OOMKilled` (exit 137) in its own pod; the Celery task and the other pod task of the same run succeeded, and no worker restarted |
| Failed pods | n/a | kept (`delete_worker_pods_on_failure = False`); `kubectl logs` on the pod still shows the task's structured stdout |

The pod's per-task overhead is pod creation, image start, and a fresh parse of the DAG file inside the pod (`dag_file_parse_ms` 1243 in the pod's log), so each pod task pays roughly 3–6 s that a warm Celery worker does not.
With an image that is not cached on the node, pod start would add the pull time on top.

## Other differences seen while setting it up

- A task that names an executor the deployment does not have is an import error (`UnknownExecutorException`) on the DAG processor, so the experiment DAG defines itself only when `[core] executor` lists KubernetesExecutor; turning the overlay off makes it disappear instead of breaking.
- Turning the second executor on changes no metric name here: Airflow 3.3 already labels the executor gauges with `executor_class_name` (and emits a `_CeleryExecutor`-suffixed copy) with a single executor, so the dashboard shows one series per executor either way.
- KEDA's worker query counts every `running` or `queued` task instance in queue `default`, whatever its executor, so pod tasks also count towards the Celery worker target; with many pod tasks KEDA would add Celery workers that sit idle.
- The chart builds the pod template from the `workers` values, so pod tasks inherit the worker image, DAG delivery (git-sync init container or the DAG volume), remote logging, and the pod-IP hostname without extra configuration.

## Verdict

Keep Celery as the default and only executor (D5).
The lab's tasks are thin orchestration calls (HTTP to EL Factory, launching dbt pods), where a warm Celery slot starts in under a second and a pod per task adds seconds of overhead and a new failure mode (a hard kill loses the remote log).
Per-task isolation matters only for a task that does heavy work itself, and the platform rule is that Airflow never processes: heavy work belongs in EL Factory or in a dbt pod, which the `run_dbt` seam already isolates with KubernetesPodOperator.

## What transfers to Composer

- Composer runs Celery workers only; there is no KubernetesExecutor to choose.
- The isolation tool on Composer is `KubernetesPodOperator` (or a Cloud Run Job, as the dbt seam plans), which is exactly how the lab isolates heavy work already.
- The lesson that a hard-killed task can lose its remote log carries over: on GKE and Composer, Cloud Logging collects the pod's stdout, which survives the pod; read it there when the task log in the UI is missing.
