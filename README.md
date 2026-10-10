<img src="assets/icon.svg" width="64" height="64" alt="">

# pplk8s

A single-machine lab for running Apache Airflow 3 on Kubernetes.
It rehearses moving a GCP data platform from Cloud Workflows to Airflow, first self-managed on GKE and later on Cloud Composer.
Every GCP service has a local stand-in, and all data is public or synthetic.

```
trigger → Airflow DAG → EL Factory (extract, stage in object storage, load warehouse) → dbt (bronze → silver → gold → exposed) → readiness record
```

Airflow only orchestrates: extraction lives in EL Factory and transformation in dbt.
DAGs reach those workloads through one thin seam (`airflow/include/pplk8s/`), so they can move to Composer unchanged.

**Status:** Phases 0–6 are done (toolchain, containers, Kubernetes, Airflow via Helm, the scheduled ELT DAG, event-triggered runs, and operating it like production: monitoring and alerts, remote logs, KEDA, git-sync and CI, failure drills).
Phase 7 (a real GCP touchpoint) is parked; see [`PLAN.md`](PLAN.md).

## Layout

| Path | What it holds |
|---|---|
| `platform/compose/` | Out-of-cluster "managed services": Postgres warehouse (BigQuery) and metadata DB (Cloud SQL), fake-gcs (GCS), Pub/Sub emulator |
| `platform/kind/` | kind cluster (the GKE stand-in) and local image registry |
| `platform/k8s/` | Workloads namespace: EL Factory Deployment, event adapter, dbt Job template |
| `platform/helm/airflow/` | Official Airflow chart values, overlays, and deploy script |
| `platform/monitoring/` | kube-prometheus-stack, scrape targets, alert rules, Grafana dashboard |
| `platform/keda/` | KEDA, which scales the Celery workers |
| `.github/workflows/` | CI (lint, tests, image builds) and the kind integration test |
| `services/el-factory/` | EL Factory lite, the extraction service (Flask) |
| `services/event-adapter/` | Pub/Sub file events → exactly-once Airflow runs |
| `dbt/` | Medallion dbt project and its image |
| `airflow/` | DAGs, the shared workload seam, Airflow image, unit tests |
| `tests/e2e/` | One exit check per phase |
| `docs/` | [Runbook](docs/runbook.md) of failure drills, [event path](docs/events.md), [executor comparison](docs/executors.md) |

## Prerequisites

- Linux or WSL2 with Docker (Docker Desktop with WSL integration works; give it at least 8 CPUs and 16 GiB).
- `kubectl`, `make`, `curl`, `jq`, and [`uv`](https://docs.astral.sh/uv/) on `PATH`.
- `~/.local/bin` on `PATH`; `make tools` installs pinned `kind`, `kubectl`, `helm`, and `k9s` there.
- For git-sync DAG delivery (the default), a read-only deploy key on the GitHub repo at `~/.ssh/pplk8s-deploy` (`platform/helm/airflow/deploy.sh` prints the commands); without one, deploy with `DAG_DELIVERY=local`.

## Quick start

```bash
make tools          # pinned kind, helm, k9s
make cluster-up     # kind cluster + registry on localhost:5001
make workloads-up   # Compose services, images, EL Factory + event adapter in namespace workloads
make airflow-up     # Airflow 3.3.1 via the official chart in namespace airflow
make airflow-ui     # http://localhost:8080 (admin/admin)
make observability-up grafana-ui   # Prometheus, Grafana on http://localhost:3000 (admin/admin)

make test           # unit tests and linters for every Python package, no cluster needed
make phase4-check   # sales_elt end to end, idempotent re-runs, failure drills (~15 min)
make phase5-check   # file event → exactly one run, redelivery no-op, cross-pipeline wait (~3 min)
make phase6-check   # dashboards, KEDA scaling, every failure drill: alert fires, runbook recovers (~35 min)

make cluster-down services-down
```

Every phase has a `make phaseN-check` exit check; run `make help` for all targets.

## Working files

- [`PLAN.md`](PLAN.md): roadmap, architecture decisions, pinned versions, and phase exit criteria.
- [`LEDGER.md`](LEDGER.md): append-only log of completed work.
- [`LESSONS.md`](LESSONS.md): lessons that carry over to the real GKE and Composer build.
- [`CLAUDE.md`](CLAUDE.md): principles and conventions for agents working in this repo.
