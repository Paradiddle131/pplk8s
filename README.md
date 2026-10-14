<img src="assets/icon.svg" width="64" height="64" alt="">

# pplk8s

Apache Airflow 3 on Kubernetes, orchestrating a GCP-style ELT platform on one machine.
Every managed GCP service has a local stand-in; all data is public or synthetic.

<img width="2318" height="1250" alt="Architecture: Airflow, workloads and monitoring namespaces in the cluster; metadata DB, Pub/Sub, object storage and warehouse outside it" src="https://github.com/user-attachments/assets/ccacd37d-60c0-47dd-a4ca-8f621519c2c4" />

## Design

- **Airflow orchestrates, never processes.** Extraction runs in EL Factory, transformation in dbt; DAGs pass only identifiers and status.
- **One seam.** DAGs reach workloads only through `airflow/include/pplk8s/`, so swapping a stand-in for the real GCP operator never touches a DAG.
- **Managed services stay outside the cluster**, as they do on GCP.
- **Re-runs are safe.** Every load is idempotent; Airflow is the single retry owner.

| Here | On GCP |
|---|---|
| kind, 1 control plane + 2 workers | GKE |
| EL Factory (Flask Deployment) | Cloud Run service |
| dbt pod via `KubernetesPodOperator` | Cloud Run Job |
| Postgres warehouse | BigQuery |
| Postgres metadata DB behind PgBouncer | Cloud SQL |
| fake-gcs | Cloud Storage |
| Pub/Sub emulator | Pub/Sub |

## Pipelines

| DAG | Trigger | Does |
|---|---|---|
| `sales_elt` | `@daily` | Extract → load → dbt bronze, silver, gold, exposed |
| `returns_file_arrival` | File event (Pub/Sub → event adapter) | One file → exactly one run |
| `finance_daily` | `@daily`, defers on upstream readiness | Joins sales and returns once both are ready |
| `tlc_monthly` | Monthly, backfillable | NYC TLC trip files, resumed chunk by chunk, built month by month |

## Stack

| Layer | Components |
|---|---|
| Orchestration | Airflow 3.3.1, official Helm chart 1.22, CeleryExecutor, 2 schedulers, 2 triggerers, git-sync DAGs, remote logs |
| Scaling | KEDA 2.21: Celery workers 1–4 |
| Transformation | dbt-core 1.12, medallion layers + `ops` readiness ledger |
| Observability | kube-prometheus-stack, StatsD and SQL exporters, ~30 alert rules, Grafana dashboard |
| Platform | Kubernetes 1.36 (kind), local registry, Docker Compose for the out-of-cluster services |

<img width="1929" height="2102" alt="k9s: all pods running across the airflow, keda, monitoring and workloads namespaces" src="https://github.com/user-attachments/assets/c9603099-4f1d-47b8-adfe-a0ff00d8fff2" />

## Prerequisites

- Linux or WSL2 with Docker, at least 8 CPUs and 16 GiB.
- `make`, `curl`, `jq`, [`uv`](https://docs.astral.sh/uv/); `~/.local/bin` on `PATH`.
- A read-only deploy key at `~/.ssh/pplk8s-deploy` for git-sync, or `DAG_DELIVERY=local`.

## Quick start

```bash
make tools              # pinned kind, kubectl, helm, k9s
make cluster-up         # kind cluster + registry on localhost:5001
make workloads-up       # out-of-cluster services, images, EL Factory, event adapter
make airflow-up         # Airflow + KEDA
make observability-up   # Prometheus, Alertmanager, Grafana

make airflow-ui         # http://localhost:8080  admin/admin
make grafana-ui         # http://localhost:3000  admin/admin

make cluster-down services-down
```

## Checks

| Command | Verifies |
|---|---|
| `make test` | Unit tests, DAG import, linters, alert-rule tests; no cluster |
| `make verify` | `test` + every image build; the merge gate |
| `make phase4-check` | `sales_elt` end to end, idempotent re-runs, retry drills |
| `make phase5-check` | File event → one run, redelivery is a no-op |
| `make phase6-check` | Dashboards, KEDA scale-out/in, every failure drill |
| `make phase8-check` | `tlc_monthly` scheduled and backfilled months reconcile |

`make help` lists every target.

## Layout

| Path | Holds |
|---|---|
| `airflow/` | DAGs, the workload seam, Airflow image, tests |
| `services/el-factory/` | Extraction service |
| `services/event-adapter/` | Pub/Sub → Airflow REST, exactly once |
| `dbt/` | dbt project and image |
| `platform/` | kind, Compose, Helm values, workloads manifests, KEDA, monitoring |
| `tests/` | End-to-end checks and alert-rule tests |
| `docs/` | [Runbook](docs/runbook.md), [event path](docs/events.md), [executors](docs/executors.md) |
| [`PLAN.md`](PLAN.md) | Architecture decisions and version pins |
