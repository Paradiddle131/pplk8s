# Phase 5 — Events and cross-pipeline dependencies

Status: approved 2026-10-10 (adapter + AssetWatcher spike; partner returns domain); in progress.
Roadmap entry: [`PLAN.md`](../PLAN.md) §5 Phase 5.
Delete this file once Phase 5 is `done` and its LEDGER entry records the evidence.

## Goal and exit

Exit (from PLAN.md): dropping one file triggers exactly one scoped run; re-delivering the same event does not reprocess the same generation.
Also in scope: a consumer DAG that waits (deferrable) on `ops.readiness`, and a written comparison of Airflow Assets with the durable ledger.

## Facts verified before planning

- fake-gcs-server 1.56.1 publishes object events itself: flags `-event.pubsub-project-id`, `-event.pubsub-topic`, `-event.bucket`, `-event.object-prefix`, `-event.list` (default `finalize`).
  Message attributes: `bucketId`, `objectId`, `objectGeneration`, `eventType`, `eventTime`, `payloadFormat`; data is the object resource JSON with `generation`.
  It uses the Go Pub/Sub client, which honours `PUBSUB_EMULATOR_HOST`; it never creates the topic, so the topic must exist first.
- Pub/Sub emulator image: `gcr.io/google.com/cloudsdktool/google-cloud-cli:588.0.0-emulators` (newest numbered `-emulators` tag on 2026-10-10).
- Google provider 22.4.0 (our pin) ships a Pub/Sub `MessageQueueTrigger` (`google+pubsub` scheme) for `AssetWatcher` event scheduling: an in-Airflow alternative to an adapter, recorded in the comparison below.

## Decisions

D17–D20 are recorded in [`PLAN.md`](../PLAN.md) §3; this file only tracks the work.

## Work units (dependency order)

1. **Event plumbing in Compose** — `platform/compose/compose.yaml`, `platform/compose/up.sh`.
   Add `pubsub` (emulator, `:8085`, host `127.0.0.1:8085`), a one-shot `pubsub-init` that PUTs topic `gcs-object-events` and pull subscription `file-arrivals` (ack deadline 60 s) via the emulator REST API, and the fake-gcs `-event.*` flags scoped to bucket `landing`, `finalize` only, with `PUBSUB_EMULATOR_HOST=pubsub:8085` and `depends_on: pubsub-init: service_completed_successfully`.
   `up.sh` also creates bucket `landing`.
   Risk: medium (start ordering; fake-gcs may drop events silently if the topic is missing).
   Check: upload an object with curl, pull the subscription via emulator REST, see one message with the right `objectGeneration`.
2. **EL Factory `POST /load`** — `services/el-factory/` (app, a `files` source module, warehouse table `ds_source.partner_returns`, catalog, README, tests).
   Body `{bucket, object, generation, entity, run_id}`; reads exactly that generation (`?generation=`), parses NDJSON, loads idempotently keyed by `(_source_uri, _generation)` (delete + insert in one transaction under the existing advisory lock).
   A superseded generation is 409 `{"retryable": false, "superseded": true}`; the hook turns it into a skip, because the newer generation has its own event and run.
   Verified on 2026-10-10 against fake-gcs 1.56.1: `?alt=media&generation=<current>` → 200, an overwritten generation → 404 (same as real GCS on a non-versioned bucket).
   Risk: medium.
   Check: `cd services/el-factory && uv run pytest -q`, then a curl `/load` twice against Compose, row count unchanged.
3. **Seam extensions** — `airflow/include/pplk8s/`: `ElFactoryHook.load_file`, `run_dbt(layer, *, pipeline="sales")` with the D20 selection, `file_loads` ledger helpers (`already_loaded`, `record_file_load`), `ReadinessTrigger` + `wait_for_readiness` deferrable sensor (polls `ops.readiness` for `product`, interval, `status='ready'`, optional minimum watermark; timeout → fail).
   Warehouse DDL for `ops.file_loads` in `warehouse-init` plus an idempotent apply for the existing volume.
   Image tag bump (D16) to `3.3.1-pplk8s.4`.
   Risk: medium (trigger serialisation and async DB access in the triggerer).
   Check: `make airflow-test` with new unit tests (trigger serialise round-trip, poll ready/not-ready/timeout, selection strings, ledger SQL).
4. **dbt models** — tag existing models `sales`; add `returns` models (`brz_partner_returns`, `slv_returns`) and `finance` model (`exp_net_sales_daily` = `gold.daily_sales` minus returns).
   Risk: low.
   Check: `make dbt-build STAGE=...` per tag combination and `dbt build` of each pipeline's layers against the Phase 4 data.
5. **DAGs** — `airflow/dags/returns_file_arrival.py` (`schedule=None`; validate `conf` → `already_loaded` short-circuit → `load_file` → dbt `returns` bronze/silver → `record_file_load` + readiness `returns.silver`); `airflow/dags/finance_daily.py` (`@daily`; `wait_for_readiness("sales.gold")` and `("returns.silver")` deferrable → dbt `finance` exposed → readiness `finance.exposed`).
   Risk: low.
   Check: DagBag test, `dag.test()`-style unit tests for the short-circuit path.
6. **Event adapter** — `services/event-adapter/` (Python, `google-cloud-pubsub` streaming pull, `requests`), routing ConfigMap (`returns/` → `returns_file_arrival`), Deployment in namespace `workloads`, API credentials Secret, Makefile `events-up`.
   Run id: `gcs__<bucket>__<object-slug>__<generation>` with a short hash when the slug would exceed Airflow's length limit.
   Risk: medium (JWT expiry handling; ack semantics).
   Check: unit tests for routing, run-id derivation, and the ack/nack table; then the e2e check.
6b. **AssetWatcher spike** — second pull subscription `file-arrivals-assetwatcher` on the same topic (created by `pubsub-init`); `airflow/dags/returns_asset_watch.py`: an `Asset` with `AssetWatcher(MessageQueueTrigger(scheme="google+pubsub", ...))`, `schedule=[asset]`, one task that only logs the triggering event's `{bucket, object, generation}` (no load, so the production path stays the single writer).
   `apache-airflow-providers-common-messaging` 2.0.4 and `google-cloud-pubsub` 2.39.1 are already in image `3.3.1-pplk8s.3` (via the constraints); pin the provider explicitly in `airflow/requirements.txt` (D3) and set `PUBSUB_EMULATOR_HOST` on the triggerer.
   Risk: high (unknown whether the async Pub/Sub client honours the emulator; finding out is the spike's point, and a negative result is recorded, not worked around).
   Check: upload a file → one asset event and one spike run per message; record the observed redelivery, ack, and dedupe behaviour against D18.
7. **Exit check** — `tests/e2e/phase5-check.sh` + Makefile `phase5-check`, reusing `tests/e2e/lib/airflow-api.sh`:
   (a) upload `returns/2026-10-09.jsonl` → exactly one `returns_file_arrival` run with matching `conf.generation`, succeeded, rows = file lines;
   (b) republish the same event (emulator REST publish with identical attributes) → still one run;
   (c) delete that dag run, republish → a new run that short-circuits, row count unchanged;
   (d) re-upload changed content (new generation) → one new run, rows replaced, not added;
   (e) trigger `finance_daily` for an interval whose `sales.gold` is not ready → sensor `deferred`, triggerer holds it, no worker slot used → record readiness → run succeeds.
   Pass twice in a row, as in Phase 4.
8. **Docs** — `docs/events.md` (event path, D18 dedupe table, Assets vs ledger vs AssetWatcher comparison), runbook drills (topic missing, adapter down → backlog drains on restart, poison message), PLAN.md decisions and status, LEDGER entry.

## Open questions

None blocking; D17–D20 are the forks and each has a recommendation above.
