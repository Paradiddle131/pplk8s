# LESSONS — experience to carry into Airflow on GKE and Cloud Composer

This file distils what the pplk8s lab taught, for agents and engineers building the real platform.
The lab itself is Stage 1 in [`PLAN.md`](PLAN.md): a local rehearsal on stand-ins.
These lessons target Stage 2 (self-managed Airflow on GKE) and Stage 3 (Cloud Composer), with EL Factory on Cloud Run, dbt as a Cloud Run Job, BigQuery, GCS, Pub/Sub/Eventarc, Terraform, and GitHub Actions.
Anything that only mattered on the laptop (WSL2, Docker Desktop, kind host mounts, local ports, reboots) is deliberately left out.
Each line is one lesson: imperative, generic, and backed by something that actually happened in the lab.
Append new lessons under the matching heading as later phases run; keep one line each, and drop a lesson when it is proven wrong.

## Versions and dependencies

- Pick the Airflow version the managed target actually ships (Composer's list), not Apache's newest; re-check before every bump.
- Composer's default image can lag its newest Airflow line; choose the line deliberately, because starting on the old major means learning a soon-legacy architecture.
- Pin provider versions to what Composer preinstalls, so DAG code imports what production will have.
- Install under the official Airflow constraints file for your Python line, and when a pinned provider conflicts, drop only the conflicting constraint lines, say so in the Dockerfile, and run `pip check`.
- Pin every provider you import, even one the base image already ships; an unpinned transitive provider disappears from a test env or a rebuild without warning.
- Keep the local test environment's pins identical to the image's, or accept and document that transitive versions differ.
- Verify Composer's Python minor before assuming the image's; the lab never confirmed it.
- Override the Helm chart's Airflow image explicitly: the chart's default appVersion trails the Airflow release you want.
- Pin the GKE minor to the release channel you will run (Regular by default), and record the source and date of every version fact.
- Pin dbt-core and the adapter as a pair, and nest generic-test arguments under `arguments:` (dbt 1.12 deprecates the flat form).

## Airflow 3 code

- Import from the Task SDK (`airflow.sdk`, `airflow.sdk.exceptions`); the `airflow.exceptions` paths are deprecated in Airflow 3.
- Tasks never touch the metadata DB; Composer 3 workers cannot reach it, so anything that needs run state goes through the REST API or task context.
- Resolve environment-specific values (image, namespace) from Variables in Jinja templates at run time, so DAG parsing never queries the metadata DB.
- `HttpHook.run` sends GET query parameters through `data=`, not `params=`.
- Give HTTP calls a `(connect, read)` timeout tuple; a short connect timeout turns a blackholed connection during a service rollout into a fast, retryable failure instead of a two-minute hang.
- Give even trivial first tasks (context resolution, catalog fetch) a retry budget; a transient blip there fails the whole run.
- Keep shared DAG code in one importable package, and keep DAG files thin enough that the DagBag import test catches every missing module.

## DAG design

- Airflow orchestrates; extraction stays in the extraction service and transformation in dbt, and XCom carries identifiers and compact summaries only.
- Reach workloads only through a thin seam (one hook, one task factory), so swapping KubernetesPodOperator for `CloudRunExecuteJobOperator` changes one module and no DAG.
- Let the extraction service own the source catalog; the DAG asks for it at run time and maps over it, never copying it.
- Map one task per source/entity with `expand`, label map indexes (`source.entity`), and cap concurrency against the shared service with a pool.
- Run one dbt task per layer or selection, never per model; dbt owns the model graph.
- Select dbt work by pipeline tag intersected with layer tag (`tag:<pipeline>,tag:<layer>`); folder selection quietly builds every pipeline's models in that layer.
- Tag singular tests with the same pipeline and layer tags as their models, and set `indirect_selection: cautious`, so a stage never runs a test that needs a later stage.
- When you narrow a selection, prove it builds exactly the same tables by comparing content hashes before and after.
- Clearing one dbt stage can drop dependent views (`DROP ... CASCADE` on rebuild); clear it together with its downstream stages.
- Disable catchup unless a backfill policy exists; unpausing a `catchup=False` DAG immediately creates the latest scheduled run.
- New DAGs start paused; deployment or test scripts must unpause explicitly and restore the flag afterwards.
- Allow several active runs when runs mostly wait in deferral, and serialise only the conflicting task with `max_active_tis_per_dag=1`; `max_active_runs=1` lets one waiting run block every other interval.
- Validate event payloads in the first task and fail fast with a non-retryable exception; a malformed event never becomes valid on retry.

## Retries and idempotency

- Name a single retry owner: Airflow task retries; the service classifies faults (`retryable: true` 503 vs non-retryable 4xx/502/500) and never retries internally.
- Map retryable faults to ordinary exceptions (task retries apply) and permanent ones to `AirflowFailException` (fail at once, no retries spent).
- Treat a connection error or a 5xx without the service's JSON body as retryable: it came from the platform (gateway, rollout), not the service.
- Make every task attempt restartable from scratch: restart pagination at page 0, and let page 0 clear the whole `(run_id, interval)` slice before loading.
- Load idempotently per slice (delete + insert in one transaction under an advisory lock), so a retry after a failure on page N duplicates nothing.
- Do not use `dbt retry` from an orchestrator: it needs the previous invocation's `run_results.json`, which dies with the ephemeral pod or Cloud Run Job execution; re-run the idempotent stage instead.
- Guard pagination in the client: refuse a repeating cursor, cap the page count, and accept a `next_url` only on the same host.
- Validate service responses strictly (status, integer counts, bool is not int) and fail fast on anything malformed.
- Before recording readiness, compare loaded rows with the count the service reported, and fail fast on a mismatch.
- Prove idempotency with data, not run status: rows equal distinct keys per run, and gold/exposed count:hash values unchanged after clear-and-rerun.
- Expect a killed worker's task to stay `running` until the task heartbeat timeout (~5 min by default) before it is retried; tune that timeout knowingly.
- Inject faults before any side effect, and for a "retry then succeed" drill inject 100% failure, then lift it mid-retries; a fractional rate over many requests makes the outcome random.

## Events and file arrival

- Exactly-once comes from idempotency, never from delivery: Pub/Sub delivers at least once.
- Derive the run id deterministically from `(bucket, object, generation)` plus a short hash of the exact object name; Airflow then rejects a redelivery with 409.
- Ack an event after Airflow accepted (2xx), recognised (409), or permanently rejected (other 4xx) it; nack on 5xx, network errors, and 404 (the DAG may not be parsed yet).
- Back the run-id dedupe with a durable file-load ledger keyed by object generation: check it first, short-circuit if loaded, and write it as the last task.
- Read exactly the event's object generation; on a non-versioned bucket an overwritten generation is gone (404), so the run should skip, not fail, because the newer generation has its own event.
- Never let an older generation's load overwrite a newer one: guard the loader with a per-object lock and a max-generation check.
- Derive a file run's processing interval from a validated pattern in the object name, so its readiness record lines up with scheduled consumers.
- A GCS notification publisher never creates its topic, and a publish to a missing topic drops the event silently; monitor the topic and the GCS service agent's publish permission.
- Make the event adapter exit when its streaming pull dies, so the orchestrator restarts it; run one replica with a `Recreate` rollout, because the subscription buffers the backlog.
- An adapter outage delays runs but loses nothing while messages stay within subscription retention; replay lost events by republishing the notification for the object's live generation.
- `AssetWatcher` with the Pub/Sub `MessageQueueTrigger` turns one pull into one asset event and one run (three messages became one run), acks on pull before any run exists, and has no routing or dedupe key; prefer an adapter when you need one run per file.
- The provider's Pub/Sub trigger resolves Google credentials before building its client; against an emulator, give it a connection with `is_anonymous: true`, and set `PUBSUB_EMULATOR_HOST` on the triggerer, where it runs.

## Cross-pipeline readiness

- Keep readiness in a durable warehouse ledger (product, interval, watermark, run id, status), not in Airflow metadata; Assets live in one deployment and carry no interval or watermark.
- Write readiness as an UPSERT on `(product, interval_start, interval_end)`, so a re-run rewrites the same row.
- Publish one readiness product per layer plus one for the whole run, so a consumer waits for exactly the layer it reads.
- Consumers know only ledger product names, never producer DAG ids, so a producer can move to another environment or tool unchanged.
- Wait with a deferrable sensor: check once on the worker, then defer to a trigger that polls the ledger from the triggerer; the waiting task holds no worker slot.
- In a custom trigger, wrap the synchronous hook query in `sync_to_async`, serialise only plain values (ISO timestamps), and ship the trigger's module in the image the triggerer runs.
- Bound every cross-pipeline wait with a sensor timeout, and expect scheduled consumers to time out on intervals whose producers never ran.

## Helm chart and Kubernetes (Stage 2)

- Run the chart's migration and create-user Jobs without Helm hooks when installing with `--wait`: with hooks, Helm waits for pods that wait for the migration hook, a deadlock.
- Jobs are immutable: delete finished chart Jobs before each upgrade and use `--wait-for-jobs`.
- `airflow db migrate` only moves forward: a `helm rollback` restores manifests, not the schema.
- A `helm rollback` creates a new revision number; read the history, do not expect the old number back.
- Preview every upgrade with `helm diff`, and test the rollout path by changing a value that feeds the chart's config checksum.
- Use the chart's renamed worker keys (`workers.celery.*`); the old ones only warn.
- Lower the Celery workers' `terminationGracePeriodSeconds` from the chart's 600 s when tasks are short; one stuck pod otherwise stalls a rollout for ten minutes.
- Keep worker pod names stable (StatefulSet): the API server fetches task logs from workers by pod name.
- Keep every generated secret (fernet, JWT, API secret, connections) in Kubernetes Secrets created once by the deploy script and never rotated by a re-run; a rotated JWT secret breaks running tasks.
- Changing a Secret consumed through `envFrom` does not roll pods; restart the workloads, or hash the Secret into a pod annotation.
- Treat image tags as immutable and bump them on every change, across every manifest and default that names the image; with `IfNotPresent`, a same-tag rebuild never reaches running pods.
- Enable PgBouncer in front of an external metadata DB, and keep the bundled Postgres subchart off.
- Give workload pods the `restricted` profile: non-root uid, seccomp `RuntimeDefault`, drop ALL, no privilege escalation, read-only root with emptyDirs for scratch, and no service-account token unless they call the API.
- Roll Pod Security out in `warn` mode first, then `enforce`.
- Server libraries may write under `$HOME` (gunicorn's control socket); a non-root, read-only image needs that feature disabled or a writable path.
- Keep workload Deployments at two replicas with `maxUnavailable: 0` and real probes, so a bad image tag or failing probe leaves the old pods serving.
- Give one-shot Jobs a unique name per run, `ttlSecondsAfterFinished`, `backoffLimit`, and `activeDeadlineSeconds`.
- A worker hostname arrives as a pod FQDN; match it by prefix.
- Grant the Airflow worker ServiceAccount a Role only in the namespace where it launches pods, and remember that deleting that namespace deletes the Role too.
- Choose the executor for orchestration throughput and isolation; Celery fits thin HTTP and pod-launch tasks and matches Composer's model.

## Shipping DAGs and images

- Ship DAG files and the shared package they import as one versioned unit: a DAG folder that syncs ahead of the image (or Composer's `dags/` ahead of its plugins or PyPI packages) produces import errors on every component.
- Never edit DAGs in a live-synced location while a run or check depends on it.
- A DAG whose file vanished still answers `GET /dags/<id>` with `is_stale: true`, but triggering it returns 404; check `is_stale` before you trigger, and alert on it.
- Check import health from the DAG processor (`airflow dags list-import-errors`), not only from the UI.
- Make deploy scripts idempotent: create pools and connections on every run.
- Use `postgresql://` in connection URIs (Airflow normalises it), and pass JSON-form connections when extras are needed.
- Keep lab-default credentials out of real environments; the chart's create-user Job gives `admin`/`admin`, and an event adapter needs its own API identity.
- Keep emulator switches (`STORAGE_EMULATOR_HOST`, `PUBSUB_EMULATOR_HOST`) out of real manifests: they switch clients to anonymous credentials or insecure channels.

## Warehouse and dbt

- Create every landing table at service startup (best effort) and again before each load, so dbt sources resolve on a fresh warehouse before the first extract.
- Load the warehouse from the staged object, not from in-memory rows, to mirror a GCS-to-BigQuery load.
- Keep file-sourced tables keyed by object and generation, not by run interval.
- Dedupe silver with a deterministic order (latest `_loaded_at`, then a tie-breaker) so re-landed rows resolve the same way every time.
- Keep dbt SQL portable to BigQuery, and mark each dialect-specific line with a comment naming the BigQuery form.
- Run `dbt parse` in the image build as a smoke check, and drive connection settings from env vars so one image serves every environment.
- An intermittent "dbt was unable to infer all dependencies" failure was seen and never reproduced; give dbt tasks retries and avoid concurrent builds against the same target.

## Testing and verification

- Count work as done only when its check passes, and require two consecutive passes for long end-to-end checks.
- Unit tests are not enough: run the built image and the real platform; non-root, socket, and connection-timeout faults appeared only there.
- Reproduce a failure end to end and read the actual error body before fixing anything; a hidden HTTP body (404 for a stale DAG) looked like a generic trigger failure.
- Make e2e helpers print API error bodies; `curl -f` alone hides why a call failed.
- Assert on structured values (counts, states, hashes), not on regexes over text output.
- Prove a fixture's assumption before asserting on it, and soak-test a stage sequence; one green run hid an intermittent failure.
- Make checks re-runnable and self-restoring: fresh run ids, restored config and paused flags in an exit trap that also fires on SIGINT/SIGTERM.
- Never let a check delete state a real producer owns; detect it and refuse to run instead.
- Drill failures for real (kill a worker, inject 503s, break a probe, drop a topic) and record what you observed, not what you expected.
- A port-forward binds to one pod; restart it after every rollout.
- Fetch a mapped task's logs with `?map_index=` on the task path, not the index in the path.
- Re-run a verification script after any edit to it, and verify a delegated agent's report against the raw logs before relying on it.

## Process

- Record a decision with its rationale in the plan before building on it, and change the plan before changing course.
- Keep project instructions to invariants; versions and status belong in the plan and the work log.
- Surface genuine forks (event adapter vs AssetWatcher) to the owner instead of deciding silently; a spike built side by side settled it with evidence.
- Treat identity, IAM, Workload Identity, and private networking as their own workstream on real GCP; the lab deferred them on purpose.
- Keep EL Factory and dbt on Cloud Run when Airflow moves to GKE; moving them onto the Airflow cluster makes the Composer step harder.
