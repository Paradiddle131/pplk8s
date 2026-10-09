# LEDGER

Append-only log of completed work, oldest first.
Add one entry at the end of every working session that changed the repo; never rewrite past entries, correct them with a new one.

Entry format:

```
## YYYY-MM-DD — <phase> — <one-line summary>
- Done: what changed (files/components).
- Evidence: the check that passed (command + observed result).
- Decisions: any PLAN.md decision added or changed, with its ID.
- Open: anything left unfinished or discovered, and where it is tracked.
```

## 2026-10-09 — Planning — initial plan, ledger, and agent instructions
- Done: wrote `PLAN.md` (goal, architecture, decisions D1–D12, phases 0–7), `LEDGER.md`, `CLAUDE.md`.
- Evidence: Airflow target verified against Cloud Composer release notes (Airflow 3 GA on Composer 3 since 2026-04-15; newest builds `composer-3-airflow-3.3.1` and `3.2.2` as of 2026-09-25) and the Airflow Helm chart release notes (1.22.0, 2026-06-01).
- Decisions: D1–D12 established.
- Open: Phase 7 (real GCP spend) parked pending user decision.

## 2026-10-09 — Phase 0 — toolchain, skeleton, kind cluster with local registry
- Done: `scripts/install-tools.sh` (checksum-pinned kind v0.33.0, helm v3.22.0, k9s v0.51.0 into `~/.local/bin`); `platform/kind/` (cluster config, `cluster-up.sh`, `cluster-down.sh`, `cluster-check.sh`); `Makefile` (`tools`, `lint`, `cluster-up/down/check`); target directory layout; `.gitignore`; README prerequisites.
- Evidence: Docker Desktop 29.5.3 via WSL integration, 28 CPUs / 31 GiB visible.
  `make cluster-up` → 3 nodes Ready on v1.36.4 in ~60 s; `make cluster-check` → 2 Ready workers, busybox pushed to `localhost:5001` and run as a pod in-cluster; `make cluster-down` → no clusters, no leftover containers; down/up/check cycle repeated cleanly; `make lint` (shellcheck) clean.
- Decisions: D4 refined with the concrete pins (Kubernetes 1.36.4 = GKE Regular default, registry `registry:3` on `localhost:5001`).
- Open: none.
  Fixed during the session: workers were not yet Ready right after `kind create --wait` (it waits only for the control plane); `cluster-up.sh` now waits for all nodes.

## 2026-10-09 — Phase 1 — Compose stand-ins, EL Factory lite, dbt medallion project
- Done: `platform/compose/` (Postgres 18.6 warehouse on `localhost:5433` with datasets as schemas and `ops.readiness`; fake-gcs-server 1.56.1 on `localhost:4480` with bucket `staging`); `services/el-factory/` (Flask + gunicorn, non-root multi-stage image, synthetic and Open-Meteo sources, the §3 contract, 49 unit tests); `dbt/` (dbt-core 1.12.5 + dbt-postgres 1.11.0, bronze → silver → gold → exposed with tests and per-stage selectors, own image); `scripts/el-factory-local.sh`; `tests/e2e/phase1-check.sh`; Makefile targets `services-up/down/reset`, `build`, `el-factory-up/down`, `dbt-build`, `test`, `phase1-check`.
- Evidence: `make services-reset && make phase1-check` → 3 objects staged in fake-gcs, 200 customers and 73 orders in `ds_source`; re-running `phase1__check` left counts unchanged (3:200:73); a re-run with fewer pages left exactly 73 orders; `dbt build --select` bronze, silver, gold, exposed all pass; `gold.daily_sales` 2 rows, `gold.customer_lifetime` 200, `exposed.sales_by_country_daily` 12.
  The check passed 5 times in a row before the review fixes and again after them.
  A manual Open-Meteo run (3 pages × 48 rows) flowed through to `exposed.daily_sales_with_weather`.
  Stopping the warehouse made `/extract` answer 503 with `retryable: true`.
  A fresh clone passes `make lint`, `make test`, and both image builds.
- Decisions: §3 EL Factory contract updated to the built behaviour (extra response fields, page-0 reset, error classes, `enabled` flag, `FAIL_RATE`).
- Open: fake-gcs advertises `-external-url=http://gcs:4443` for resumable uploads, so pods in kind must resolve `gcs` once the cluster joins the Compose network (Phase 2).
  An intermittent "unable to infer all dependencies" dbt failure reported while the project was being built could not be reproduced in ~170 isolated runs (including 60 fixed `PYTHONHASHSEED` values); it coincided with concurrent runs against the same scratch database; re-open if a stage fails that way again.
  Stale staged objects from a re-run with fewer pages stay in GCS (rows are cleaned, files are not); acceptable for a staging bucket.
