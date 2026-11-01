## 2026-11-01 — Maintenance — `make airflow-down` passes when no Airflow release is installed

- Done: `airflow-down` uninstalls with `--ignore-not-found`, as `keda-down` and `observability-down` already do, so a cleanup chain such as `make airflow-down workloads-down services-reset` no longer stops at a release an earlier run removed.
- Evidence: see the PR.
- Decisions: none.
- Open: none.
