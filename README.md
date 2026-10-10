<img src="assets/icon.svg" width="64" height="64" alt="">

# pplk8s

A local learning lab for running Apache Airflow on Kubernetes, mimicking a GCP data platform.
See [`PLAN.md`](PLAN.md) for the roadmap and [`LEDGER.md`](LEDGER.md) for progress.

## Prerequisites

- Linux or WSL2 with Docker (Docker Desktop with WSL integration works; give it at least 8 CPUs and 16 GiB).
- `kubectl`, `make`, `curl`, `jq`, and [`uv`](https://docs.astral.sh/uv/) on `PATH`.
- `~/.local/bin` on `PATH`; `make tools` installs pinned `kind`, `helm`, and `k9s` there.

## Quick start

```bash
make tools          # install pinned kind, helm, k9s
make cluster-up     # kind cluster (1 control plane, 2 workers) + registry on localhost:5001
make cluster-check  # verify workers are Ready and in-cluster pulls from the registry work
make cluster-down   # remove the cluster and the registry

make services-up    # warehouse Postgres (localhost:5433), fake-gcs (localhost:4480), Pub/Sub emulator (localhost:8085)
make build          # EL Factory lite, dbt, and event adapter images
make el-factory-up  # EL Factory lite on localhost:8090
make dbt-build STAGE=gold
make phase1-check   # end-to-end Phase 1 exit check

make workloads-up   # EL Factory, event adapter, dbt Job inputs in namespace workloads (pods reach Compose by name)
make dbt-job STAGE=gold
make phase2-check   # in-cluster extract + dbt Jobs for every stage

make airflow-up     # Airflow 3.3.1 via the official chart in namespace airflow
make airflow-ui     # http://localhost:8080 (admin/admin)
make phase3-check   # hello DAG on a Celery worker, helm diff/upgrade/rollback
make airflow-test   # DAG and seam unit tests (local uv env, no cluster)
make phase4-check   # sales_elt end to end + idempotent re-runs + kill and FAIL_RATE drills (~12-18 min)
make phase5-check   # file event -> exactly one run, redelivery no-op, deferrable cross-pipeline wait (~3 min)
```

Start order does not matter: `cluster-up` and `services-up` both attach the kind nodes to the Compose network.
Failure drills and their observed symptoms live in [`docs/runbook.md`](docs/runbook.md); the event path is explained in [`docs/events.md`](docs/events.md).

Run `make help` for every target.
