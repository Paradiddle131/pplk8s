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

## 2026-10-10 — Phase 6 — observability stack and remote task logs
- Done: `platform/monitoring/` (kube-prometheus-stack 92.3.0 values, `deploy.sh`, Kustomize manifests: `ServiceMonitor`s for `airflow-statsd` and `airflow-pgbouncer`, a `ScrapeConfig` for the Compose databases, `PrometheusRule` `airflow` with 14 alerts, dashboard "Airflow overview" as a ConfigMap); Make targets `observability-up`, `observability-down`, `grafana-ui`, `prometheus-ui`.
  Compose: `metadata-db-exporter` and `warehouse-exporter` (postgres_exporter v0.20.1) beside the databases; `up.sh` creates bucket `airflow-logs`.
  Airflow values: statsd-exporter on with InfluxDB-style tags, two histogram mappings replacing the chart's Airflow 2 ones, cache TTL 5 m (1 h for histograms); remote task logs to `gs://airflow-logs` through connection `gcs_logs` and `STORAGE_EMULATOR_HOST` on every component; workers are a Deployment with no log PVCs and report their pod IP as hostname; `deploy.sh` restarts the exporter when its mappings change and deletes the StatefulSet's leftover log PVCs.
  `pplk8s.emulator_logging` (logging config for the emulator only) and `pplk8s.context.run_interval`, which anchors a run triggered with `"logical_date": null` on its `run_after` (it failed with `KeyError: 'logical_date'` before).
  e2e: `lib/prometheus.sh`, `observability-check.sh`; `run_hello` and `worker_pod` moved into `lib/airflow-api.sh`; the Phase 3 upgrade drill no longer assumes `worker_concurrency = 16`.
  Image `3.3.1-pplk8s.9` (`.7`/`.8` were intermediate builds of this session).
- Evidence: StatsD tags were confirmed on the live exporter before any dashboard: `airflow_pool_open_slots{pool_name="el_factory"} 7`, `{pool_name="default_pool"} 128`, `airflow_task_duration_seconds_bucket{dag_id="hello",task_id="say_hello",…}`.
  Corrections to the prep research: executor gauges carry an `executor_class_name` label (and a `_CeleryExecutor`-suffixed copy) even with one executor, and 3.3.1 still emits legacy per-pool names (`airflow_pool_open_slots_el_factory`) next to the tagged ones.
  Without a TTL the exporter kept one `triggers_running` series per triggerer pod ever seen (sum 8 instead of 2); the chart did not restart the exporter for `overrideMappings` changes, so the TTL only took effect after a manual restart.
  The first remote-log upload failed: `Refusing to overwrite remote log gs://airflow-logs/…: could not read existing content (404 … Not Found)`; after the shim, `hello`'s log was in the bucket, its worker pod was deleted, and `GET …/taskInstances/say_hello/logs/1` still returned the log with source `gs://airflow-logs/dag_id=hello/…/attempt=1.log`.
  `tests/e2e/observability-check.sh` passed: 18 dashboard series present with their labels, pools are separate series, 14 Airflow alert rules loaded and none firing, Grafana lists "Airflow overview".
  The dashboard was checked in a browser and fixed until it read cleanly (stat titles, units, axis ranges, per-container memory against dashed limits).
  The default rule `AlertmanagerClusterCrashlooping` fired with zero restarts: on WSL2 `process_start_time_seconds` creeps ~2.5 s every 30 s; disabled in the values.
  A `sales_elt` run triggered with `"logical_date": null` now succeeds; `make test` → Airflow 102, EL Factory 69, event adapter 32 passed.
- Open: the worker's working set (~860 MiB) exceeds its 768 Mi request; resource tuning comes with KEDA.

## 2026-10-10 — Phase 6 — KEDA scaling and resource tuning
- Done: `platform/keda/` (KEDA 2.21.0 values and `deploy.sh`, operator metrics with a ServiceMonitor when the monitoring CRDs exist); Make targets `keda-up`, `keda-down`, and `airflow-up` now depends on `keda-up`.
  Airflow values: `workers.celery.keda` (min 1, max 4, polling 5 s, cooldown 60 s, HPA scale-down stabilisation 120 s, query through PgBouncer), `worker_concurrency = 4`; pool `ops_load` (16) from `deploy.sh`.
  Fixture DAG `ops_load_test` (mapped tasks that only hold a slot, `retries=0`, own pool) and `tests/e2e/keda-check.sh`.
  e2e guard `require_synced_dags` (runs from `start_port_forward`): with git-sync a check refuses to run unless the local `airflow/` equals the served commit.
- Evidence: `tests/e2e/keda-check.sh` passed: workers at 1, 16 tasks × 45 s triggered at 15:49:16, 4 workers available at 15:49:39 (23 s), run succeeded in 72 s with 16/16 tasks successful on try 1, workers back at 1 109 s after the run (HPA events: 1 → 4, 4 → 3, 3 → 1).
  Resource tuning from Prometheus (`max_over_time` of `container_memory_working_set_bytes` over 45 minutes covering the Phase 4 drills, a `sales_elt` run and the burst), memory request before → after: worker 768Mi → 1Gi (peak 1005Mi), dag-processor 512Mi → 640Mi (peak 617Mi), triggerer 384Mi → 576Mi and limit 768Mi → 1Gi (peak 553Mi), scheduler 512Mi → 384Mi (peak 369Mi), api-server 768Mi → 384Mi and limit 1536Mi → 1Gi (peak 337Mi); CPU peaks stayed at 0.3–0.45 cores, so CPU requests are unchanged.
  KEDA reported `FailedGetExternalMetric` twice during an Airflow redeploy (the scaler reads the connection from the worker pod template being replaced); it recovered by itself.
- Open: no scale-in happened while tasks were still running (the stabilisation window held the workers until the burst ended); a forced scale-in mid-task is left to the drills.

## 2026-10-10 — Phase 6 — KubernetesExecutor experiment
- Done: overlay `platform/helm/airflow/values-multi-executor.yaml` (`CeleryExecutor,KubernetesExecutor`), `make airflow-up AIRFLOW_OVERLAYS=…`; DAG `ops_executor_experiment` (defined only when KubernetesExecutor is configured), `tests/e2e/executor-experiment.sh`, and the write-up `docs/executors.md`.
- Evidence: three experiment runs passed: queued → running 0 s / 0 s / 1 s on Celery vs 2 s / 5 s / 5 s for a pod; trivial-task duration 0.08 s vs 1.4–1.5 s (the pod re-parses the DAG file, `dag_file_parse_ms` 1243); `on_kubernetes`'s pod was deleted and its log still came from `gs://airflow-logs`.
  `exceed_memory` (600 MiB in a 384Mi pod) failed alone: scheduler log `container_reason: OOMKilled … exit_code: 137`, the Celery and other pod tasks of the run succeeded, no worker restarted; its remote log was lost (`Could not read served logs … timed out`), while `kubectl logs` on the kept failed pod still showed the task's stdout.
  A task naming an unconfigured executor is an import error (`UnknownExecutorException`), hence the conditional DAG; a unit test covers both cases.
  The overlay was removed (`executor = CeleryExecutor`) and `tests/e2e/phase5-check.sh` passed again.
- Decisions: D5 stands; verdict and Composer translation in `docs/executors.md`.

## 2026-10-10 — Phase 6 — failure drills, runbook, exit check, and close-out
- Done: `tests/e2e/phase6-check.sh` (drills 1–4: scheduler scaled to 0, node drain, metadata DB stop, pool slot starvation, worker OOMKill; each injects, waits for its alert, recovers per the runbook, waits for the resolve, and runs the `hello` canary) and `tests/e2e/phase6-upgrade-drill.sh` (drill 5: chart 1.21.0 + Airflow 3.2.2 → 1.22.0 + 3.3.1 on throwaway database `airflow_drill`, `helm diff`, `pg_dump` before the upgrade, the wrong way back with `helm rollback` alone, the right way back with restore + redeploy).
  `make phase6-check` runs `observability-check`, `keda-check`, both drill scripts; `make phase6-upgrade-drill` and `make airflow-drill-image` (image `3.2.2-pplk8s.2`, Composer 3.2.2 provider pins in `airflow/requirements-drill-3.2.2.txt`, the Dockerfile takes the version as a build arg).
  New alerts `AirflowRolloutStuck` and a rewritten `AirflowMigrationJobFailed`; `task_instance_heartbeat_timeout` 120 s; the emulator logging shim copies the default remote log IO field by field (3.2.2's provider has no `from_config`), image `3.3.1-pplk8s.11`.
  `docs/runbook.md` "Phase 6 drills" with an entry per drill (trigger, observed symptoms, detecting alert and panel, diagnosis, recovery); PLAN D24/D25/D28 as-built notes and §4 layout; README status, layout, and quick start; LESSONS gained Observability, Upgrades, and scaling sections.
  PR #1 (WU0–WU6) merged into `main` after CI and the kind integration passed; `.prep/phase6/` deleted.
- Evidence: `make phase6-check` passed twice in a row against git-sync of `main` (commit `1f761346`), 21:17–21:46 and 21:47–22:15.
  Pass 2: scheduler down detected in 111 s, resolved 26 s after recovery; drain detected in 34 s, every pod rescheduled, none Pending; metadata DB detected in 58 s, scheduler heartbeating 32 s after the DB returned; pool starvation detected in 86 s; OOMKill detected and resolved in 181 s; KEDA 1 → 4 → 1 (back at 1 after 124 s); upgrade drill: `AirflowMigrationJobFailed` 95 s after the rollback, `AirflowRolloutStuck` 112 s later, restore + redeploy back on schema `1d6611b6ab7c`.
  The first rollback rehearsals fired nothing: `AirflowComponentUnavailable` stayed quiet because the old pods kept serving, and a first `AirflowRolloutStuck` on updated replicas stayed quiet because a crash-looping new pod counts as updated; `kube_job_status_failed` stayed 0 because the chart's Job restarts in place. The final expressions were back-tested with range queries over the three rehearsals before the next run.
  The migration pod logged `Can't locate revision identified by 'd2f4e1b3c5a7'`; new pods' `wait-for-airflow-migrations` logged `MigrationHead(s) in DB: {'d2f4e1b3c5a7'} | Migration Head(s) in Source Code: {'1d6611b6ab7c'}`.
  The first exit pass failed in `observability-check` (`no series for airflow_ti_successes`): it waited on a 1 h-TTL histogram while the 5-minute counter had expired; it now polls each series.
  An earlier drill pass reported no restarts during the DB outage because its counter was broken; the fixed counter shows the scheduler (killed by its liveness probe, exit 143), dag-processor, and triggerer (exit 1) restarting 1–3 times each.
  `make test` → Airflow 106, EL Factory 69, event adapter 32 passed; `make lint` clean.
- Open: #2 (PgBouncer is one replica; the drain that moved it restarted the triggerer once), #3 (a KEDA scale-in during a running task is never exercised).

## 2026-10-10 — Phase 6 — Grafana OOMKill on wide dashboard ranges

- Done: Grafana's memory request 192Mi → 320Mi and limit 384Mi → 768Mi (`platform/monitoring/values.yaml`); LESSONS gained a Grafana sizing line.
- Evidence: switching *Airflow overview* off its default range ended `make grafana-ui` with `connection refused` inside the pod; the grafana container had `lastState.terminated.reason: OOMKilled` (exit 137) at 20:40:45 UTC, after idling near 268 MiB and peaking at 343 MiB.
  After `make observability-up`, the dashboard loaded at 6 h, 2 d, and 7 d in a browser through `make grafana-ui`, with 0 restarts and a 542 MiB peak.
- Open: #5 (Prometheus misses rule evaluations every ~4.5 min, so `PrometheusMissingRuleEvaluations` keeps firing).

## 2026-10-10 — LESSONS reorganised for Stages 2 and 3

- Done: `LESSONS.md` gained a stage matrix and **[GKE]**/**[Composer]** line tags, a "Migrating from Cloud Workflows" section (one pipeline at a time, parity by data, a way back, deferrable long waits), and "Design choices to settle at work" (DAG boundaries, dbt granularity, extraction fan-out, with what to weigh).
  Merged duplicates: the two heartbeat-timeout lines, the two PodDisruptionBudget lines, the Grafana and request-sizing lines, the two per-model dbt lines; "keep EL Factory and dbt on Cloud Run" moved into the migration section.
- Evidence: the live scheduler reports `create_cron_data_intervals = False`, and scheduled `sales_elt` runs carry no data interval, so the interval lesson now names the tested helper (`pplk8s.context.resolve_interval`) instead of "a run starts when its interval ends".

## 2026-10-11 — PgBouncer survives a node drain (#2)

- Done: PgBouncer runs two replicas with preferred anti-affinity across the nodes and a PodDisruptionBudget `maxUnavailable: 1` (`platform/helm/airflow/values.yaml`); drill 2 of `tests/e2e/phase6-check.sh` now fails if any Airflow container restarts during the drain.
  PLAN D6, the runbook's drill 2 entry, and the LESSONS PgBouncer line record the result.
- Evidence: baseline with one replica, six evictions of the lone PgBouncer pod in a row restarted the scheduler, dag-processor, and triggerer once each.
  With two replicas, eight evictions one replica at a time restarted nothing, and draining each node by hand (components moving with it) restarted nothing; with both replicas on one node, the drain waited on the PDB and evicted them one at a time.
  `make phase6-check` passed, 23:51–00:20: drill 2 drained `pplk8s-worker2`, moved 1 of 2 PgBouncer replicas while the triggerer, dag-processor, and api-server stayed on the other node, and no container restarted; drills 1, 3, 4a, 4b, the upgrade drill, KEDA, and observability checks passed as before.

## 2026-10-11 — Vertical sizing lessons

- Done: `LESSONS.md` gained a Helm/Kubernetes line (fix a per-request memory spike with a higher limit, not replicas) and a [GKE] design choice on where the Vertical Pod Autoscaler fits (recommend-only widely; automatic resizing only for multi-replica stateless services with gradual growth).
- Evidence: the Grafana OOMKill fixed in `685bf90` (one pod, 384 Mi limit, a wide dashboard range); the VPA line is reasoning, not a lab run, so it sits under "Design choices to settle at work".

## 2026-10-11 — Phase 6 — KEDA scale-in during a running task (#3), and a frozen scaler

- Done: `tests/e2e/keda-check.sh` adds a scale-in drill: raise the ScaledObject minimum by one, run one `ops_load_test` task, mark its pod with `controller.kubernetes.io/pod-deletion-cost: "-100"`, drop the minimum back; once with a task shorter than the 60 s grace and once with a longer one.
  PgBouncer gets `max_prepared_statements = 100` (`pgbouncer.extraIni`), which stopped KEDA's PostgreSQL scaler from failing most polls with `prepared statement "stmtcache_…" already exists`.
  `validate_event` (returns_file_arrival) and both `ReadinessSensor`s (finance_daily) gained retries, and `test_every_business_task_survives_a_lost_worker` asserts `retries ≥ 1` on every task of the three business DAGs.
  Runbook drill 6, PLAN D24 and D6, and three LESSONS lines record the result.
- Evidence: before the PgBouncer change, `keda-operator` logged 714 prepared-statement errors in 30 minutes, the HPA reported `FailedGetExternalMetric`, and a worker idle since 10:55:46 was only removed at 10:59:31; after it, none.
  `tests/e2e/keda-check.sh` passed, 11:08–11:17: burst 1 → 4 workers in 28 s, 16/16 tasks on try 1, back to 1 worker 130 s after the run; the scale-in picked the marked pod after 13 s and the 45 s task succeeded during the warm shutdown; with a 240 s task the scale-in picked the marked pod after 10 s, the pod was gone after 77 s (60 s grace), and the scheduler failed the task 121 s later on its heartbeat timeout.
  `make airflow-test` (109 passed) and `make lint` passed.
- Decisions: D24 keeps `terminationGracePeriodSeconds: 60` and makes `retries ≥ 1` on every business task the contract instead (Composer also ends in-flight tasks when it removes workers); D6 records `max_prepared_statements`.
- Open: #7 (no alert when the KEDA scaler fails; Prometheus does not scrape KEDA).

## 2026-10-11 — Phase 6 — Alert when KEDA's scaler fails (#7)

- Done: `KedaScalerErrors` (`keda_scaled_object_errors_total` rising in every 1-minute window for 2 minutes) and `KedaMetricsMissing` (the operator not scraped) in a new `airflow.scaling` rule group; a "Scaling" dashboard row with "KEDA scaler failed polls /min" and "KEDA worker target vs workers"; runbook drill 7; and drill 7 in `tests/e2e/phase6-check.sh`, which breaks the worker trigger's query, asserts the worker count stays put, restores it, and waits for the alert to resolve.
  KEDA's ServiceMonitor moved from the KEDA chart (enabled only if the monitoring CRDs already existed, so `make phase6-check`'s order, KEDA before monitoring, left KEDA unscraped on a fresh lab) into `platform/monitoring/manifests/airflow-monitors.yaml`.
  `observability-check.sh` also requires `keda_scaler_metrics_value` and treats a firing `Keda*` alert as unhealthy.
  PLAN D24 and D28, runbook drills 3, 6 and 7, and two LESSONS lines record the result.
- Evidence: during the prepared-statement clash `keda_scaled_object_errors_total` counted 198 failed polls while `keda_scaler_detail_errors_total` stayed at 0, so the alert uses the first; back-tested over 08:35–09:00 UTC, the expression held throughout (it would have fired around 08:37).
  `make phase6-check` passed, 11:41–12:18: observability (19 series, 17 rules, none firing), KEDA (1 → 4 → 1, both scale-in cases), drills 1–4b as before, drill 7 `KedaScalerErrors` firing after 147 s with 15 failed polls a minute, ScaledObject `Ready=False`, HPA `FailedGetExternalMetric`, workers unchanged, resolved 57 s after the restore, canary passed; the upgrade drill passed.
  `KedaScalerErrors` also fired during drill 3 (the metadata DB stop), as it should.
  By hand, the operator scaled to 0 fired `KedaMetricsMissing` after about 2.5 minutes and it resolved once the operator was back.
- Open: #9 (Prometheus keeps its TSDB on emptyDir, so drill 2's drain wiped every series older than the drain).


## 2026-10-11 — Phase 6 — Prometheus keeps its history across a restart (#9)

- Done: Prometheus' TSDB moved from the operator's default emptyDir to a 5Gi PVC on kind's `standard` StorageClass (`storageSpec.volumeClaimTemplate`, `retentionSize: 4GB`), and Prometheus runs on the control plane (`nodeSelector` plus a toleration), because a `local-path` PV is pinned to its node and a worker drain would leave Prometheus Pending during the drill it observes.
  Drill 2 in `tests/e2e/phase6-check.sh` records a pre-drain `count(up)` sample, restarts Prometheus after the drain, and fails unless the same sample still reads back (`prom_value_at` in `tests/e2e/lib/prometheus.sh`).
  PLAN D21, runbook drill 2, and one LESSONS line record the result.
- Evidence: `make observability-up` let the operator recreate the StatefulSet itself; the PV landed on `pplk8s-control-plane`.
  `make phase6-check`, 12:36–13:09: observability, KEDA, and drills 1–4b and 7 passed; drill 2 drained `pplk8s-worker2`, then the restarted Prometheus read `count(up)` at 12:51:55 as 28, the same as before.
  Afterwards the pod was 10:54:33 UTC old and its oldest sample 10:39:34 UTC, the first start on the volume.
  The upgrade drill in that run timed out installing the old line (#11); `make phase6-upgrade-drill` then passed on its own, 13:27–13:36.
  `make lint` passed.
- Decisions: D21 keeps Prometheus on the control plane with a node-pinned volume instead of a shared host mount for a node-independent PV (closer to a GKE persistent disk, but it needs a cluster rebuild and a WSL2 bind mount that can come up empty).
- Open: #11 (upgrade drill step 1 timed out once after the other drills).

## 2026-10-11 — Phase 6 — Upgrade drill: no PgBouncer roll across a database switch (#11)

- Done: `tests/e2e/phase6-upgrade-drill.sh` gained `stop_airflow` (every Deployment to 0, PgBouncer pods deleted at once instead of after their 120 s preStop sleep) and calls it before each deploy that moves PgBouncer between `airflow` and `airflow_drill`: step 1, step 4, the final restore and the exit trap.
  On failure the exit trap now prints the migration Job's logs (current and previous attempt) and a waiting scheduler's `wait-for-airflow-migrations` log before it redeploys.
  Runbook drill 5 and one LESSONS line record the cause.
- Evidence: root cause reproduced with a log watcher on a standalone drill, 13:59–14:08.
  In step 1 PgBouncer rolled while the 3.2.2 migration Job ran; two attempts reached the lab's `airflow` database through an old PgBouncer pod and failed with `Can't locate revision identified by 'd2f4e1b3c5a7'` (the 3.3.1 head of `airflow`) before a third reached `airflow_drill`.
  The final restore's 3.3.1 Job ran `Running upgrade 1d6611b6ab7c -> …` on `airflow_drill`, not `airflow`, and reported success.
  Each failed attempt adds to the container's restart backoff (10 s doubling to 300 s), which with a slower roll after the other drills explains the 10-minute timeout of #11.
  With the fix, `make phase6-check` passed three times in a row, 14:09–14:50, 14:50–15:30 and 15:30–16:12; step 1 took 2.5–3 minutes each time, its Job never met the wrong schema (only `Connection refused` for the ~13 s before the new PgBouncer was ready), and the final restore's Job ran no upgrade.
  `make lint` passed.

## 2026-10-11 — Phase 6 — False `PrometheusMissingRuleEvaluations` on WSL2 (#5)

- Done: root-caused the always-firing `PrometheusMissingRuleEvaluations` to the WSL2 VM's clocks, not to load.
  `platform/monitoring/values.yaml` disables the rule next to `AlertmanagerClusterCrashlooping`, which has the same cause.
  `platform/monitoring/manifests/prometheus-rules.yaml` adds `PrometheusRuleGroupOverrun`, which fires when a group evaluation outlasts its interval.
  `tests/e2e/observability-check.sh` now also fails on any firing `Prometheus.*` alert.
  PLAN D21 and one LESSONS line record the cause.
- Evidence: reproduced on the live lab, 14:12 UTC: `increase(prometheus_rule_group_iterations_missed_total[30m])` was 8.05 for each of 34 groups, and the alert was firing on 33 series, while the slowest group evaluation took 0.035 s.
  Sampling `time.time() - time.monotonic()` every 15 s showed the wall clock stepping forward by ~2.08 s every ~32 s, i.e. ~6.5% fast against the monotonic clock (clocksource `tsc`, Hyper-V TimeSync active); the wall clock agreed with an external HTTP `Date` header.
  Prometheus 3.15.0 ticks each group on a monotonic `time.Ticker` but computes `missed := time.Since(evalTimestamp)/interval - 1` from a wall-clock-only `evalTimestamp` (`rules/group.go`), so wall time gains one 15 s slot every ~3.8 minutes: a predicted 7.8 misses per group per 30 minutes against 8.05 observed.
  After `platform/monitoring/deploy.sh`, the old alert's series went stale, the new rule loaded with `health=ok`, and only `Watchdog` was firing; the check's firing query returned `PrometheusMissingRuleEvaluations` at 14:23 and nothing at 14:27.
  `tests/e2e/observability-check.sh` and `make lint` passed.
- Open: the clock itself is a host issue outside the repo; switching the WSL2 kernel to `clocksource=hyperv_clocksource_tsc_page` might fix it but is untested (needs root).

## 2026-10-11 — Phase 6 — Drill 8: restart the Celery broker

- Done: a new failure drill for the one Airflow component no drill or alert covered, the chart's Redis broker (a StatefulSet without persistence).
  `AirflowTasksStuckQueued` (task instances in `queued` for 3 minutes) is new, and `AirflowComponentUnavailable` now covers StatefulSets.
  The worker liveness probe moved from the chart's 60 s x 5 to 30 s x 3 (`workers.celery.livenessProbe`).
  `tests/e2e/phase6-check.sh` gained drill 8a (KEDA paused at 0 workers, `hello` queued in Redis, Redis restarted, alert fires, the task is cleared and succeeds) and 8b (Redis restarted under a 240 s task, `hello` must succeed within 5 minutes).
  Runbook drill 8, PLAN D29, and three LESSONS lines record the result; issue #15 tracks the worker stall's root cause.
- Evidence: exploration on the live lab, 14:39–15:07 UTC.
  With all 12 tasks running, a Redis restart cost nothing (workers reconnected in 3 s, all on try 1).
  A message waiting in Redis was lost: `plan` stayed `queued` 11 minutes with no alert until the scheduler requeued it (`Task stuck in queued; will try to requeue`, 600 s timeout plus its 120 s check); `airflow_pool_queued_slots{pool_name="default_pool"}` read 1 throughout, which the new rule back-tests on.
  Under a 480 s task, the worker took no new task after the restart and stopped answering `inspect ping`; `hello` waited 5.5 minutes until the old probe restarted the worker (exit 137), which killed the long task.
  An idle worker was unaffected.
  The Airflow source caps stuck-in-queued requeues at 2 (`num_stuck_in_queued_retries`) and fails the third, so `task_queued_timeout` stays 600 s.
  `make phase6-check` passed twice in a row, 17:22–18:14 and 18:14–19:05, every drill and the upgrade drill included.
  Pass 1, 17:22–18:14: 8a fired after 202 s, the cleared `say_hello` succeeded 5 s later on try 2, resolved after 22 s; in 8b the worker stopped answering pings, the 30 s x 3 probe restarted it, `say_hello` succeeded 150 s after the restart (330 s with the chart's probe), and the 240 s task failed.
  Pass 2: 8a fired after 200 s, recovered in 5 s, resolved after 27 s; 8b again took the probe-restart branch, `say_hello` after 144 s.
  A standalone run of drill 8 at 15:11 showed the other branch of 8b: the worker kept answering pings, took no new task until the 240 s task ended, and `say_hello` succeeded after 256 s.
  `make lint` passed.
- Decisions: D29 keeps Redis without persistence and `task_queued_timeout` at 600 s, detects lost messages by alert, recovers by clearing the task, and shortens the worker probe.
- Open: #15 (a worker that ran a task through a broker restart takes no new task until it ends).

## 2026-10-11 — Phase 6 — Worker stall after a Celery broker restart, root-caused and fixed (#15)

- Done: two causes found and fixed for a worker that ran a task through a Redis restart.
  `platform/helm/airflow/values.yaml` sets `[celery_broker_transport_options] socket_timeout = 10` and points `[celery] celery_config_options` at the new `airflow/include/pplk8s/celery_config.py`: Airflow's default Celery config plus a wrapper around `AsynPool.flush` that backports celery/celery#10346 and switches itself off on Celery ≥ 5.7.
  `airflow/tests/test_celery_config.py` covers the wrapper.
  Drill 8b in `tests/e2e/phase6-check.sh` now requires `hello` within 60 s, no worker restart, and the 240 s task to succeed.
  Image tags bumped (D16): `3.3.1-pplk8s.12`, drill image `3.2.2-pplk8s.3`, both bake the new module for host-path delivery.
  Runbook drill 8, PLAN D29, and two LESSONS lines updated; issues #17 (triggerer drill) and #18 (git-sync staleness) filed.
- Evidence: a minimal Celery 5.6.3 + Redis setup outside Airflow reproduced the first cause: `hello` was received 2 s after the reconnect but ran on `ForkPoolWorker-4` only when the 120 s task there ended; it stalled the same with `worker_enable_prefetch_count_reduction=False`, `worker_disable_prefetch=True`, and `task_acks_late=False`, while `worker_cancel_long_running_tasks_on_connection_loss=True` ran it in 4 s by cancelling the long task.
  The backport ran `hello` 1 ms after receipt on an idle process, and the long task succeeded.
  Celery 5.7.0b1 (which has the upstream fix) crashed the worker on the first ack after the reconnect (`kombu/transport/redis.py` `_connparams`: `'NoneType' object has no attribute 'hostname'`).
  In the lab, the second cause dominated: in 4 of 4 runs (baseline and backport alone) the worker stopped answering pings and the probe killed it and the 240 s task; a `SIGUSR1` stack dump showed the main thread blocked in kombu's `_brpop_read` on a dead socket.
  With `socket_timeout` alone, pings kept working and the task survived, but `hello` waited 234 s; with both fixes, three runs started `hello` 2–5 s after it was queued, with no restart and the 240 s task succeeding on try 1.
  `DAG_DELIVERY=local make phase6-check` passed 20:55–21:41 UTC, upgrade drill included: 8b `say_hello` succeeded 10 s after the broker restart (144–330 s before), 0 worker restarts, the 240 s task `success`.
- Decisions: D29 amended (socket timeout, backport as a stated stopgap until the constraints reach Celery 5.7).
- Open: drop `pplk8s.celery_config` when the Airflow constraints move to Celery ≥ 5.7.

## 2026-10-12 — Phase 6 — Drill 9: kill the triggerer under a deferred readiness wait (#17)

- Done: drill 9 in `tests/e2e/phase6-check.sh` and `docs/runbook.md`.
  A `finance_daily` run on the interval [2026-09-30, 2026-10-01) defers both readiness waits; 9a SIGKILLs the triggerer job process and marks `sales.gold` ready during the gap, 9b scales the triggerer to 0 and marks `returns.silver` ready while it is down.
  9a asserts the dead job never ended (a real crash) and that the trigger was claimed only after its heartbeat was `triggerer_health_check_threshold` stale; 9b asserts `AirflowTriggererDown` fires, the wait stays `deferred` with its trigger on the stopped job, then resumes on scale-up, the run succeeds, and `finance.exposed` is recorded.
  `make phase6-check` now also depends on `workloads-up` (the drill builds the finance exposed model).
  Two LESSONS lines (Cross-pipeline readiness) and the Phase 6 drill list in PLAN updated; issues #20 (two schedulers and triggerers) and #21 (metadata DB restore drill) filed.
- Evidence: by hand first: `kubectl delete pod --grace-period=0 --force` is not a crash (the job ended cleanly, the new triggerer claimed on its first loop, 19 s from delete to resume); SIGKILL of the job process left the job `running` with no `end_date`, and the new job claimed at a heartbeat age of 31 s; a scale to 0 fired the alert after 175 s with `default_pool` running 0.
  `task_instance.trigger_timeout` is defer time + 6 h, so an outage eats into the sensor timeout.
  Drill 9 alone passed in 4 min 10 s; then the full `tests/e2e/phase6-check.sh` passed 09:01–09:34 UTC, drills 1–9: 9a claimed 15 s after the new job started at a dead-job heartbeat age of 31 s, `wait_sales_gold` 3 s later on try 1; 9b fired after 195 s, the wait succeeded 16 s after the scale-up, the alert resolved after 30 s.
  `make lint` passed.
- Decisions: none new; the drill follows D28 (sustained outage for the alert, canary after recovery).
- Open: like phase5-check, the drill unpauses `finance_daily`, so the scheduler creates the latest scheduled run, which defers until its 6 h timeout on an interval whose `returns.silver` never lands; removed by hand after this session's runs.
  37 triggerer job rows from past crashes stay `running`; harmless, `airflow db clean` removes them.

## 2026-10-12 — Phase 6 — Reconcile open items: stray scheduled runs, metadata DB retention, leaked port-forwards

- Done: PR #22 (drill 9) reviewed and merged.
  `discard_scheduled_runs` in `tests/e2e/lib/airflow-api.sh`: the exit traps of `phase5-check.sh` and `phase6-check.sh` re-pause each DAG the check unpaused, then fail and delete the scheduled runs the scheduler created for it after the check started (drill 9's open item).
  Failing first ends a deferred wait and releases its trigger; deleting removes the run, so nothing waits 6 h and no late alert fires.
  The chart's `databaseCleanup` CronJob runs `airflow db clean` daily for rows older than 60 days without archive tables (D30); `tests/e2e/db-cleanup-check.sh` (`make db-cleanup-check`, also in `make phase6-check`) seeds a crashed job row with a 61-day-old heartbeat, runs the CronJob once, and asserts it is gone and the live jobs remain.
  Port-forwards leaked from the checks themselves, three ways: `start_port_forward` backgrounded the `kc` function, so `$pf` was a subshell and killing it left `kubectl port-forward` running; `canary` restarted the forward inside `$(run_hello)`, a subshell that could not stop the parent's and whose own outlived the check; and a check whose first forward started in such a subshell (`smoke-check.sh`) never knew it owned one.
  The helpers now background `kubectl` itself, find a forward by its command line (`stop_forward`), mark ownership with a flag file keyed by `$$` (shared by every subshell of a check), let `run_hello` keep a forward that still answers (`ensure_port_forward`), and refuse to start when their port is already taken (checked with `ss`; a test connect to a closed localhost port can hang on this WSL2 host).
  Runbook drill 9 points at the CronJob; issue #23 filed.
- Evidence: drill 9 alone (preflight + 9a/9b) passed, 09:49–09:53, and its trap printed `discarded the scheduled run finance_daily/scheduled__2026-10-12T00:00:00+00:00`; afterwards no task instance was `deferred`, `queued`, `running`, or `scheduled`, and the only trigger left was the AssetWatcher spike's `PubsubPullTrigger`.
  By hand first: a failed-then-deleted scheduled `finance_daily` run turned `wait_returns_silver` from `deferred` to `failed` and its trigger row disappeared.
  `tests/e2e/phase5-check.sh` passed, then re-paused `finance_daily` and discarded its scheduled run; no port-forward was left.
  `tests/e2e/db-cleanup-check.sh` passed twice: the seeded rows went (`Checking table job`), `SchedulerJob`, `TriggererJob`, and `DagProcessorJob` rows stayed, no `_airflow_deleted__*` table remained.
  Four port-forwards from 2026-10-11 were still running at the start of the session, one holding the checks' port 18080; with the fix, starts and restarts from the parent or a subshell followed by an exit leave no `kubectl` behind, and a held port fails fast with the holder's command line.
  The first CI run of this branch failed exactly there (`FAIL: port 18080 is already in use` in `phase5-check.sh`, right after `smoke-check.sh`), which is how the third leak was found; `smoke-check.sh` then `phase5-check.sh` passed locally with nothing left running.
  `make lint` passed.
- Decisions: D30 (metadata DB retention by the chart's CronJob, 60 days, no archive).
- Open items of earlier entries, settled:
  Phase 2, workload manifests hard-code their image tags: still true (`el-factory-deployment.yaml:32`, `event-adapter-deployment.yaml:31`, `dbt-job.template.yaml:32`, `pplk8s.dbt.DEFAULT_IMAGE`); filed as #23.
  Phase 3, `deploy.sh` hard-codes the warehouse password: resolved in Phase 5 (`d84b1b4`); `deploy.sh:19` reads `WAREHOUSE_PASSWORD`.
  Phase 3, a Celery worker `Terminating` for ~10 minutes: explained, not a mystery: the chart's default `terminationGracePeriodSeconds` is 600 s, and Celery's warm shutdown waits up to that long for a running task; since `76e2820` it is 60 s (D24), and drill 6 measured a scale-in pod gone 77 s after removal with a task still running. Closed.
  Phase 4, `resolve_context` has no retries: resolved in the Phase 6 preflight (`2768e45`); every task of `sales_elt`, `finance_daily`, and `returns_file_arrival` now has `retries ≥ 1`, enforced by `test_every_business_task_survives_a_lost_worker`.
  Phase 5, an empty newer generation racing an older load: closed by argument.
  EL Factory reads exactly the event's generation, and on a bucket without versioning only the live generation is readable (`storage.py:45`), so an older load can only proceed if it read its bytes before the newer generation existed.
  It then waits only for its own per-object advisory lock and commits.
  To lose, the newer generation's whole path (fake-gcs notification, Pub/Sub, adapter, DAG run, `validate_event`, a worker slot, its own load) must finish inside that read-to-lock gap of one HTTP request, milliseconds against the seconds a run takes to be scheduled.
  The outcome would also be visible, not silent: `ops.file_loads` would record the newer generation as loaded.
  Phase 5, the adapter logs in as `admin/admin`: resolved in the Phase 6 preflight (`2768e45`, its own `event-adapter` user with role User).
  Phase 1 and Phase 5, the unreproduced dbt failures (`unable to infer all dependencies`, one `tag:sales,tag:silver` build): closed as watch items; neither recurred since: the metadata DB holds 136 successful dbt stage task instances and no failed one; re-open with the failing log if one does.
  Phase 5, leaked port-forwards: root-caused and fixed above; the earlier explanation (ad-hoc shells skip the EXIT trap) missed that the checks leaked them too.
  Phase 6, the WSL2 clocksource: deliberately left; it is a host setting outside the repo, and the alert side is handled (D21, #5).
  Phase 6, drop `pplk8s.celery_config` once the constraints reach Celery ≥ 5.7: still open; the Airflow 3.3.1, 3.3.2, and `main` constraints pin `celery==5.6.3`, and 5.7 is still pre-release (`5.7.0b1`) on PyPI.
- Open: #18 (git-sync staleness), #20 (two schedulers and triggerers, next), #21 (metadata DB restore, after #20), #23 (workload image tags).
  The 41 crashed triggerer job rows of today stay until their heartbeats are 60 days old.

## 2026-10-12 — Phase 6 — Two schedulers and two triggerers, degraded-HA alerts, re-drilled

- Done: issue #20.
  Schedulers and triggerers run two replicas each behind PodDisruptionBudgets of `maxUnavailable: 1` (D31); the dag-processor and api-server stay at one.
  `sql_exporter` beside the metadata DB counts live jobs per type (`airflow_jobs_alive`: `running` with a heartbeat under 30 s), and `AirflowSchedulerDegraded`/`AirflowTriggererDegraded` compare it with the Deployment's desired replicas, because the statsd heartbeat counters are summed over replicas and Deployment availability misses a hung process.
  `phase6-check.sh` drills became functions (`DRILLS="1 9"` runs a subset); drill 1 crashes, hangs (SIGSTOP), then stops the schedulers; drill 2 samples live jobs through the drain; drill 9 hangs, crashes, then stops the triggerers.
  Runbook drills 1, 2, 9, the overview dashboard's live/desired tiles, and LESSONS updated.
- Evidence: `make lint` passed; `make phase6-check` passed end to end in 63 min (12:00–13:03 local), with observability, KEDA, drills 1–9, `db clean`, and the upgrade drill.
  1a: one of two schedulers SIGKILLed with 12 tasks queued and 4 running; the run succeeded 95 s later with no task instance past try 1 and no history rows.
  1b: `AirflowSchedulerDegraded` fired after 169 s with the hung pod still Running; resolved 42 s after the delete.
  1c: `AirflowSchedulerDown` after 145 s.
  2: 62 samples through the drain of `pplk8s-worker`, never fewer than one live scheduler and one live triggerer; no restarts.
  9a: the survivor took the hung triggerer's wait 24 s after the SIGSTOP (heartbeat 31 s old), the wait succeeded 2 s after its upstream turned ready; `AirflowTriggererDegraded` after 167 s.
  9b: claimed once by the other triggerer 24 s after the SIGKILL; 9c: `AirflowTriggererDown` after 194 s, the wait resumed 19 s after the scale-up.
- Decisions: D31.
- Open: #21 (metadata DB restore drill, next), #18, #23, #25.
