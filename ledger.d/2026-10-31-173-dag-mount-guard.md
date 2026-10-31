## 2026-10-31 — Maintenance — a local DAG deploy stops when the cluster mounts another clone's DAGs

- Done: `platform/kind/ensure-dag-mount.sh`, which `deploy.sh` runs for `DAG_DELIVERY=local`, compares a digest of the `*.py` files the kind workers serve with this checkout's `airflow/dags` and fails, naming both paths, when they differ (#173): `cluster-up.sh` binds the creating clone's path once, so a deploy from a second clone ran its own image with the first clone's DAGs. Runbook entry "A local DAG deploy from another clone".
- Evidence: see the PR.
- Decisions: none.
- Open: none.
