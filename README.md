<img src="assets/icon.svg" width="64" height="64" alt="">

# pplk8s

A local learning lab for running Apache Airflow on Kubernetes, mimicking a GCP data platform.
See [`PLAN.md`](PLAN.md) for the roadmap and [`LEDGER.md`](LEDGER.md) for progress.

## Prerequisites

- Linux or WSL2 with Docker (Docker Desktop with WSL integration works; give it at least 8 CPUs and 16 GiB).
- `kubectl`, `make`, `curl`, and [`uv`](https://docs.astral.sh/uv/) on `PATH`.
- `~/.local/bin` on `PATH`; `make tools` installs pinned `kind`, `helm`, and `k9s` there.

## Quick start

```bash
make tools          # install pinned kind, helm, k9s
make cluster-up     # kind cluster (1 control plane, 2 workers) + registry on localhost:5001
make cluster-check  # verify workers are Ready and in-cluster pulls from the registry work
make cluster-down   # remove the cluster and the registry
```

Run `make help` for every target.
