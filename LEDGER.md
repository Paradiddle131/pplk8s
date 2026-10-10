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

## 2026-10-10 — Phase 2 — EL Factory and dbt Jobs on kind, cluster joined to the Compose network
- Done: `platform/kind/join-services-network.sh` (kind nodes join Compose network `pplk8s`, run from `cluster-up` and `services-up`); `platform/k8s/workloads/` (Kustomize: namespace `workloads`, ServiceAccounts, ConfigMap, generated fixed-name Secret `warehouse-credentials`, EL Factory Deployment + Service `el-factory:80`, every non-obvious field commented); `platform/k8s/dbt-job.template.yaml` + `dbt-job.sh`; `tests/e2e/phase2-check.sh`; `docs/runbook.md` Phase 2 drills; Makefile `push`, `workloads-up/down`, `dbt-job`, `phase2-check`.
- Evidence: a busybox pod reached `http://gcs:4443` and `warehouse:5432` by name after the join; `make phase2-check` passed three times (twice by the implementing agent, once by the lead): in-cluster paginated extract staged 3 objects through the `gcs` hostname, 200 customers and 73 orders, re-run unchanged (3:200:73), dbt Jobs bronze/silver/gold/exposed complete, `gold.daily_sales` 2, `gold.customer_lifetime` 200, `exposed.sales_by_country_daily` 12.
  Drills done for real: bad tag (`ImagePullBackOff`, old pods kept serving), failing readiness and startup probes, OOMKill at 20Mi (exit 137), missing Secret (`CreateContainerConfigError`).
- Decisions: D13 (nodes join the Compose network; pods use Compose names) and D14 (`workloads` and `airflow` namespaces).
  The kind config now mounts `airflow/dags` on the workers for D10 delivery; the cluster was recreated once for it.
- Open: the Phase 1 open item (pods must resolve `gcs`) is closed by D13.
  Workload manifests hard-code `localhost:5001/{el-factory,dbt}:0.1.0`, so overriding `ELF_IMAGE`/`DBT_IMAGE` in the Makefile does not change what the cluster runs.
  `make workloads-down` deletes the namespace and with it Airflow's Role/RoleBinding there; `make airflow-up` re-applies them.

## 2026-10-10 — Phase 3 — Airflow 3.3.1 via the official Helm chart
- Done: `metadata-db` Postgres in Compose (`localhost:5434`); `airflow/Dockerfile` (apache/airflow:3.3.1-python3.12 + provider pins from `airflow/requirements.txt` + `include/`); `platform/helm/airflow/` (`values.yaml` for chart 1.22.0, `manifests.yaml` with DAG PV/PVC and RBAC in `workloads`, `deploy.sh`, `README.md`); `airflow/dags/hello.py`; `tests/e2e/phase3-check.sh`; helm-diff v3.15.15 pinned in `scripts/install-tools.sh`; Makefile `airflow-image`, `airflow-up/down`, `airflow-ui`, `phase3-check`.
- Evidence: `make phase3-check` passed three times (twice by the implementing agent, once by the lead): hello ran on `airflow-worker-1`, `helm diff` previewed 16 changed lines, upgrade 15 → 16, rollback as revision 17, all workloads Ready, hello succeeded again; the dag-processor lists `hello` and `sales_elt` with no import errors.
  Installed providers: google 22.4.0, cncf-kubernetes 10.21.0, http 6.0.5, postgres 7.0.1; `pip check` clean.
- Decisions: D3 applied: google 22.4.0 (Composer) wins over the 3.3.1 constraints' 22.3.0; the Dockerfile drops that line and `google-cloud-aiplatform==1.163.0` (22.4.0 needs ≥ 1.164) from the constraints and installs everything else under them.
  Migration and create-user Jobs run without Helm hooks: with hooks, `helm upgrade --wait` deadlocked (pods wait for migrations, the post-install hook waits for pods); `deploy.sh` deletes finished Jobs before each upgrade and uses `--wait-for-jobs`.
  `db migrate` only moves forward, so a rollback restores manifests but not the schema (documented in the chart README).
- Open: `deploy.sh` hard-codes the warehouse password in Secret `airflow-connections` instead of following `WAREHOUSE_PASSWORD` like `workloads-up.sh`.
  A Celery worker pod once sat `Terminating` for ~10 minutes and stalled a rollout; grace period is now 60 s, root cause not found.
  Python 3.12 for the image is assumed, not verified against Composer's Python line.
  Hindsight memory was unreachable during this session (`localhost:8888` refused connections), so nothing was retained there.

## 2026-10-10 — Phase 4 — workload seam and sales_elt DAG (exit check passed once)
- Done: `airflow/include/pplk8s/` (`ElFactoryHook` with pagination, validation, and retryable/fail-fast mapping; `run_dbt` wrapping `KubernetesPodOperator` with a restricted-profile pod; `readiness` UPSERT and extraction check); `airflow/dags/sales_elt.py` (`resolve_context` → `get_catalog` → mapped `extract` in pool `el_factory` → `check_extracted` → per-stage TaskGroup `dbt_<stage>` + `record_<stage>` → `record_sales`; `@daily`, `catchup=False`); local uv test env `airflow/pyproject.toml` + `uv.lock`; `airflow/tests/`; `tests/e2e/lib/airflow-api.sh` (shared port-forward/token/REST helpers, now used by the Phase 3 check too); `tests/e2e/phase4-check.sh`; runbook Phase 4 drills; Makefile `airflow-test`, `phase4-check`; `shellcheck -x` so sourced libs are linted.
- Evidence: `make airflow-test` → ruff clean, 50 passed.
  On the cluster, `manual__2026-10-09T22:05:46.350314+00:00` succeeded with all 14 task instances on try 1 and five `ops.readiness` products.
  `tests/e2e/phase4-check.sh` passed once end to end (18 min 15 s): (a) full run, 200/200 customers and 40/40 orders, five gold/exposed tables hashed; (b) clearing extract map index 1, then `dbt_gold` with downstream, then the whole run left counts, hashes, and readiness unchanged; (c) force-deleting the worker running `extract[0]` → TI stayed `running` ~5 min (heartbeat timeout) → `up_for_retry` try 1 → `success` on try 2, counts unchanged; `FAIL_RATE=1` → 503s retried, success on try 3 after reset.
- Decisions: D15 (Airflow is the single retry owner) and D16 (immutable Airflow image tags; current tag `3.3.1-pplk8s.3`).
  Readiness products: one per stage (`sales.bronze` … `sales.exposed`) plus `sales`, so Phase 5 consumers wait on exactly the layer they read.
  `get_catalog` got retries and a 10 s connect timeout after a run failed on a connect timeout right after an EL Factory rollout.
- Open (resume here): run `make phase4-check` once more; a second consecutive pass satisfies the "passes twice" bar, then mark Phase 4 done in `PLAN.md`.
  `airflow/uv.lock` is resolved without the Airflow constraints file, so transitive versions in the local test env can differ from the image's.
  Kill detection takes ~5 min (heartbeat timeout); worth tuning in Phase 6 drills.

## 2026-10-10 — Phase 4 — exit check passed a second time; Phase 4 done
- Done: `platform/kind/ensure-dag-mount.sh` (run from `deploy.sh`, so from `make airflow-up`) restarts any kind worker whose `airflow/dags` bind mount came up empty; `tests/e2e/lib/airflow-api.sh` gained `wait_dag_ready` (waits for `is_stale=false`) and `api` now prints the HTTP error body on stderr; the Phase 3 and Phase 4 checks use `wait_dag_ready`; runbook Phase 4 drill 4 (stale DAGs after a Docker Desktop restart); `PLAN.md` Phase 4 status `done`.
- Evidence: the first attempt this session failed before any assertion with `FAIL: could not trigger sales_elt` (5 min 12 s, all prerequisites).
  Root cause: after the machine rebooted, both kind workers showed a `tmpfs` at `/mnt/pplk8s/dags` instead of the bind mount, so the dag-processor saw no files, `sales_elt` went `is_stale: true`, and `POST /dagRuns` returned 404 `Dag with dag_id: 'sales_elt' not found`; the scheduled run `scheduled__2026-10-10T00:00:00+00:00` failed at `resolve_context` for the same reason.
  `docker restart pplk8s-worker pplk8s-worker2` restored the mount.
  The re-run `make phase4-check` passed end to end (11 min 15 s, EXIT=0): (a) full run, customers 200/200, orders 40/40, `gold.daily_sales=3:68713f0d…`, `gold.customer_lifetime=200:a1bd896f…`, `gold.daily_weather=6:b9cea776…`, `exposed.sales_by_country_daily=18:fda581ca…`, `exposed.daily_sales_with_weather=3:b83a5678…`, five readiness products; (b) re-running extract map index 1, `dbt_gold` with downstream, and the whole run left everything unchanged; (c) killed worker → `extract[0]` `running` 10:16:56 → `up_for_retry` 10:22:05 → `success` on try 2 10:22:38, counts unchanged; (d) `FAIL_RATE=1` → 503s retried, both extracts succeeded on try 3.
  With the earlier session's pass, the check has now passed twice with no failing assertion in between; the one failed attempt never reached the DAG.
- Open: the check ran for ~1 minute while `airflow/dags/sales_elt.py` briefly held a Phase 5 edit incompatible with the deployed image (reverted at 10:18:37); no import error was recorded and the check passed, but DAG files must not be edited while a cluster check runs, because the folder is live-mounted.
  `resolve_context` has no retries, so a transient parse or mount problem fails the whole scheduled run at once.

## 2026-10-10 — Phase 5 — events and cross-pipeline dependencies
- Done: Compose `pubsub` (emulator `google-cloud-cli:588.0.0-emulators`, `localhost:8085`) and one-shot `pubsub-init` (topic `gcs-object-events`, subscriptions `file-arrivals` and `file-arrivals-assetwatcher`); fake-gcs publishes `finalize` events for bucket `landing`; `up.sh` creates `landing` and re-applies `warehouse-init` (new `ops.file_loads`).
  EL Factory `POST /load` (generation-pinned read, per-object replace under an advisory lock, 422 bad file, 409 `superseded`), file entity `partner_returns`.
  `services/event-adapter` (streaming pull → REST trigger, deterministic run id, ack/nack table, health endpoint) deployed in `workloads`.
  Seam: `pplk8s.context` (run context and file-event validation, moved out of `sales_elt`), `ElFactoryHook.load_file`, `ops.file_loads` helpers, `pplk8s.sensors.ReadinessSensor`/`ReadinessTrigger`, `run_dbt(stage, pipeline=...)`.
  dbt pipeline tags on every model; `brz_partner_returns`, `slv_returns`, `exp_net_sales_daily`.
  DAGs `returns_file_arrival`, `finance_daily`, and the spike `returns_asset_watch`; `docs/events.md`; runbook Phase 5 drills; `tests/e2e/phase5-check.sh`, Makefile `phase5-check`.
  Images: `el-factory`/`dbt` 0.2.0 (D16 now covers every image), `event-adapter` 0.1.0, `airflow` `3.3.1-pplk8s.5` (pins `common-messaging` 2.0.4).
  Also fixed: `deploy.sh` follows `WAREHOUSE_PASSWORD` (Phase 3 open item); the e2e library runs a check's cleanup on SIGINT/SIGTERM.
- Evidence: `make test` → Airflow 96, EL Factory 69, event adapter 32 passed; ruff and shellcheck clean.
  `make phase5-check` passed twice in a row (1 min 58 s, 1 min 55 s): (e) both waits `deferred`, `default_pool running=0 deferred=4 occupied=0`; (a) one upload → exactly one run `gcs__landing__returns_2026-10-02.jsonl__<gen>__f2f19370`, 3 rows; (b) republished event → adapter `duplicate`, still one run; (c) run deleted + republished → re-created run short-circuited (`load=skipped`), rows unchanged; (d) new generation → one new run, rows replaced (3 → 2); (e) after `sales.gold` was recorded the consumer resumed, `exposed.net_sales_daily[2026-10-02]` = `7935.20 - 14.03 = 7921.17`.
  `make phase4-check` re-passed after the `sales_elt` changes (11 min 26 s) with the same five gold/exposed hashes as before (`gold.daily_sales=3:68713f0d…` …), so the D20 selection builds exactly what Phase 4 built.
  AssetWatcher spike: works against the emulator (async client honours `PUBSUB_EMULATOR_HOST`; needs a Google connection with `is_anonymous`); one pull of three messages became one asset event and one run; messages are acked on pull.
  Drills run for real: emulator restart loses topology and silently drops events (fake-gcs logs `Topic not found` at INFO), adapter exits and restarts, replay by republishing; adapter-down backlog drains on start; poison object fails `validate_event` on try 1.
- Decisions: D17 (adapter + REST trigger; AssetWatcher as a log-only spike), D18 (exactly-once by idempotency: run id + `ops.file_loads`), D19 (deferrable wait on `ops.readiness`), D20 (dbt selection by pipeline and layer); D16 widened to all images.
  `finance_daily` allows 4 active runs with `dbt_exposed` at `max_active_tis_per_dag=1`: with 1 active run, the scheduled run created on unpause sat deferred on its own interval and blocked the manual run.
- Open: a newer generation that is an empty file leaves no `_generation` marker in `ds_source`, so an older generation's load racing it could still commit; storage already refuses overwritten generations, so the window is the read-to-commit gap.
  The scheduled `finance_daily` run for 2026-10-09 is deferred waiting on `returns.silver` for that day and will fail at its 6 h timeout unless a returns file lands; expected behaviour, but noise.
  The adapter logs in with the chart's `admin/admin`; a dedicated API user belongs with Phase 6 hardening.
  One `dbt build --select tag:sales,tag:silver` in a freshly created `dbt_dev` failed (3 errors) and could not be reproduced in three further attempts, including from an empty database; watch for it.
  Ad-hoc shells that source `tests/e2e/lib/airflow-api.sh` from the agent tool leaked `kubectl port-forward` processes (the EXIT trap does not fire there); the check scripts themselves clean up.


## 2026-10-10 — Repo tidy for the first push

- Done: README rewritten for a first-time reader (purpose, data flow, status, layout table, shortest quick start, pointers to the working files); PLAN §4 layout now matches the tree (`platform/k8s/`, `tests/e2e/`, `docs/`, `scripts/`); removed four `.gitkeep` files from directories that now have content.
- Evidence: `make test` → Airflow 96, EL Factory 69, event adapter 32 passed; ruff and `make lint` (shellcheck) clean; no credentials tracked beyond the documented lab defaults.

## 2026-10-10 — Phase 6 — preflight: decisions D21–D28, Python 3.11 and Composer build.3 pins, adapter identity
- Done: decisions D21–D28 recorded in `PLAN.md` §3, D5 and D10 refined, D16 updated for git-sync; Phase 6 `in progress`.
  `scripts/install-tools.sh` pins kubectl v1.36.5 (checksum), one minor from the v1.36.4 server; it was v1.34.1 from Docker Desktop.
  Airflow image `3.3.1-pplk8s.6`: `apache/airflow:3.3.1-python3.11` (Composer Gen 3 runs Python 3.11.8), cncf-kubernetes 10.21.1, postgres 7.0.2, common-sql 2.1.1, standard 1.18.0, fab 3.8.1, celery 3.23.1 (Composer `3.3.1-build.3`); the superseded constraint lines are dropped and `pip check` passes; `airflow/uv.lock` re-resolved for Python 3.11.
  `resolve_context` in `sales_elt` and `finance_daily` has 2 retries (Phase 4 open item).
  The event adapter logs in as its own Airflow user `event-adapter` (role User) instead of `admin`: `platform/helm/airflow/api-identity.sh` generates the password once into Secret `airflow/airflow-api-event-adapter`, `deploy.sh` creates the user, and `workloads-up.sh` hands the login to the adapter and restarts it when the login changed (Phase 5 open item).
  Deleted the stray `default/dnsprobe` pod.
- Evidence: `make test` → Airflow 96, EL Factory 69, event adapter 32 passed; ruff and shellcheck clean; in the image `python -V` = 3.11.15 and `pip list` shows the pins above.
  On the new image `tests/e2e/phase5-check.sh` passed (adapter triggered every run with its new identity), then `tests/e2e/phase4-check.sh` passed with the same five hashes as Phase 4 (`gold.daily_sales=3:68713f0d…`, `gold.customer_lifetime=200:a1bd896f…`, `gold.daily_weather=6:b9cea776…`, `exposed.sales_by_country_daily=18:fda581ca…`, `exposed.daily_sales_with_weather=3:b83a5678…`); the kill drill went try 1 killed → try 2 success, FAIL_RATE retries reached try 3.
- Decisions: D21–D28 (see PLAN.md); a read-only deploy key `pplk8s git-sync (read-only, local kind lab)` was registered on the GitHub repo for D23, its private half kept at `~/.ssh/pplk8s-deploy`.
