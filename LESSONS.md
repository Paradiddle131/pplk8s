# LESSONS — experience to carry into Airflow on GKE and Cloud Composer

This file distils what the pplk8s lab taught, for agents and engineers building the real platform.
The lab itself is Stage 1 in [`PLAN.md`](PLAN.md): a local rehearsal on stand-ins.
These lessons target Stage 2 (self-managed Airflow on GKE) and Stage 3 (Cloud Composer), which run the same DAGs on the same Airflow line, with EL Factory on Cloud Run, dbt as a Cloud Run Job, BigQuery, GCS, Pub/Sub/Eventarc, Terraform, and GitHub Actions.
Anything that only mattered on the laptop (WSL2, Docker Desktop, kind host mounts, local ports, reboots) is deliberately left out.
Each line is one lesson: imperative, generic, and backed by something that actually happened in the lab.
The exception is "Design choices to settle at work", which lists open forks and what to weigh, because the right answer depends on the real pipelines.
Append new lessons under the matching heading as later phases run; keep one line each, and drop a lesson when it is proven wrong.

## Which stage each section applies to

A section applies to the stages marked below.
Inside a section, a line that applies to only one stage starts with **[GKE]** or **[Composer]**.

| Section | Stage 2: GKE | Stage 3: Composer |
|---|---|---|
| Migrating from Cloud Workflows | yes | yes |
| Design choices to settle at work | yes | yes |
| Versions and dependencies | yes | yes |
| Airflow 3 code | yes | yes |
| DAG design | yes | yes |
| Retries and idempotency | yes | yes |
| Events and file arrival | yes | yes |
| Cross-pipeline readiness | yes | yes |
| Helm chart and Kubernetes | yes | no: Composer runs the cluster, chart, scaling, and metadata DB |
| Observability and alerting | yes | partly: Composer exports Airflow metrics to Cloud Monitoring itself |
| Upgrades and rollback | yes | partly: Composer upgrades in place |
| Shipping DAGs and images | yes | yes |
| Warehouse and dbt | yes | yes |
| Testing and verification | yes | yes |
| Process | yes | yes |

## Migrating from Cloud Workflows

- Replace only the orchestrator: EL Factory (Cloud Run service) and dbt (Cloud Run Job) keep their deployments, scaling, and resource settings, and DAGs call them the way Cloud Workflows does today; moving them onto the Airflow cluster also makes the Composer step harder.
- Inventory a workflow before porting it: its trigger (schedule or event), steps, waits, retry and timeout policies, the readiness rows it writes, and who reads them; the DAG must reproduce exactly that contract.
- Migrate one pipeline at a time, starting with the smallest and least depended-on, and treat each cutover as its own change with its own verification.
- Never let both orchestrators load the same pipeline's interval into the same tables: prove the DAG in a non-production environment or against a shadow dataset, then cut over by disabling the workflow's trigger and unpausing the DAG together.
- Prove parity with data, not run status: for the same interval, readiness rows and each layer's row counts and content hashes must match what the workflow produced.
- Keep the way back open: disable the old trigger rather than deleting the workflow, until the DAG has run its schedule cleanly for an agreed period; rolling back is pausing the DAG and re-enabling the trigger.
- Cut producers and consumers over independently; the readiness ledger is their only contract (see "Cross-pipeline readiness"), so a migrated producer can feed a consumer still on Workflows, and the other way round.
- Map every date the workflow passes onto the run's processing interval (see "Airflow 3 code"), and check one known day end to end before trusting a port.
- Translate each workflow step's retry and timeout policy into the task's `retries`, `retry_delay`, and `execution_timeout`, keeping Airflow as the only retry owner (see "Retries and idempotency").
- Never hold a worker slot through an hours-long wait: wait deferrably for dbt (`CloudRunExecuteJobOperator(deferrable=True)`). EL Factory needs no status sensor: it time-boxes each request (`MAX_RUN_TIME`) and answers `next_url`, so size the extract task's `execution_timeout` for the whole loop and keep `MAX_RUN_TIME` below the hook's read timeout (D34).

## Design choices to settle at work

These are forks the lab cannot settle; decide them per pipeline with real volumes and timings, and record the decision with its reason.

- DAG boundaries, option A: one DAG per schedule or workflow (its source/entity list, then its dbt tags), mirroring today; it is the simplest to verify against the workflow it replaces, so it is a sound default for the migration itself.
- DAG boundaries, option B: one extraction DAG per source that publishes readiness, plus schedule DAGs that wait on the sources they need and then run their dbt tags; it isolates sources from each other and makes a single source easy to re-run, at the cost of more cross-DAG waits to keep correct.
- Weigh for DAG boundaries: whether one source's failure should hold back models fed by other sources, whether a schedule tag's lineage spans several sources, how often one source is re-run alone, and how much a clear touches (a cleared dbt stage drops dependent views).
- dbt granularity: one task per schedule tag (the whole tagged lineage, as today), per tag and layer (what the lab ran: per-layer readiness and retries), or per tag and source/domain, but never one task per model, because dbt owns the model graph.
- Weigh for dbt granularity: every invocation pays a Cloud Run Job start and a parse of the whole project (more noticeable at 700+ models), a failed task re-runs its whole selection, consumers may need per-layer readiness, and parallel invocations share BigQuery slots.
- Extraction fan-out: one mapped task per source/entity (per-entity retries and visibility, more tasks) or one task per source (EL Factory iterates); size the pool from the parallelism the workflows and EL Factory already run at today, not from a guess.
- [GKE] Vertical Pod Autoscaler: run it in `Off` (recommend-only) mode widely to check hand-set requests, and let it resize pods only for multi-replica stateless services whose usage grows gradually; keep measured sizing with headroom for single replicas (VPA evicts to resize, and its updater skips workloads below two replicas), spiky user-driven load (history lags the spike), workloads an HPA scales on CPU or memory, and KEDA-scaled workers, whose `maxReplicaCount` assumes a fixed number per node.
- [GKE] Autopilot or Standard: on Autopilot Google runs the nodes and bills each pod's requests, so every container (sidecars and log groomers too) must carry requests or gets Autopilot's defaults, privileged and hostPath pods such as node-exporter are refused (use Managed Service for Prometheus), and node placement tricks like pinning Prometheus to one node do not apply; on Standard you size and pay for node pools and keep full control. Weigh who operates the nodes, cost at the platform's steady load, and whether the monitoring stack must be self-run; whichever you pick, a contended node gives each container CPU in proportion to its request, so probes and startup budgets must fit that share (D33).

## Versions and dependencies

- Pick the Airflow version the managed target actually ships (Composer's list), not Apache's newest; re-check before every bump.
- [Composer] Composer's default image can lag its newest Airflow line; choose the line deliberately, because starting on the old major means learning a soon-legacy architecture.
- Pin provider versions to what Composer preinstalls, so DAG code imports what production will have.
- Install under the official Airflow constraints file for your Python line, and when a pinned provider conflicts, drop only the conflicting constraint lines, say so in the Dockerfile, and run `pip check`.
- Pin every provider you import, even one the base image already ships; an unpinned transitive provider disappears from a test env or a rebuild without warning.
- Keep the local test environment's pins identical to the image's, or accept and document that transitive versions differ.
- Verify Composer's Python minor before assuming the image's; the lab never confirmed it.
- [GKE] Override the Helm chart's Airflow image explicitly: the chart's default appVersion trails the Airflow release you want.
- [GKE] Pin the GKE minor to the release channel you will run (Regular by default), and record the source and date of every version fact.
- Pin dbt-core and the adapter as a pair, and nest generic-test arguments under `arguments:` (dbt 1.12 deprecates the flat form).

## Airflow 3 code

- Import from the Task SDK (`airflow.sdk`, `airflow.sdk.exceptions`); the `airflow.exceptions` paths are deprecated in Airflow 3.
- Tasks never touch the metadata DB; Composer 3 workers cannot reach it, so anything that needs run state goes through the REST API or task context.
- Resolve environment-specific values (image, namespace) from Variables in Jinja templates at run time, so DAG parsing never queries the metadata DB.
- `HttpHook.run` sends GET query parameters through `data=`, not `params=`.
- Give HTTP calls a `(connect, read)` timeout tuple; a short connect timeout turns a blackholed connection during a service rollout into a fast, retryable failure instead of a two-minute hang.
- Give even trivial first tasks (context resolution, catalog fetch) a retry budget; a transient blip there fails the whole run.
- Resolve the interval a run processes in one tested helper, not in each DAG: Airflow 3 cron schedules (`create_cron_data_intervals = False`) give a run an empty interval at its fire time, and an API run may have no logical date, so the lab processes the last complete UTC day before the run; a consumer built the wrong day until it used the run whose interval holds that day.
- Keep shared DAG code in one importable package, and keep DAG files thin enough that the DagBag import test catches every missing module.
- When a run must name its data period (monthly files, backfills by month), declare `CronDataIntervalTimetable` explicitly: in Airflow 3 a cron string becomes `CronTriggerTimetable` (empty interval, logical date at the fire time, one period after the data).
- `execution_timeout` cannot be mapped (`expand_kwargs` fails with "unmappable or already specified argument", Airflow 3.3.1): size a mapped extract's per-entity time budget inside the task (the hook stops between continuations), with `execution_timeout` only as the hard stop above the largest budget.

## DAG design

- Airflow orchestrates; extraction stays in the extraction service and transformation in dbt, and XCom carries identifiers and compact summaries only.
- Reach workloads only through a thin seam (one hook, one task factory), so swapping KubernetesPodOperator for `CloudRunExecuteJobOperator` changes one module and no DAG.
- Let the extraction service own the source catalog; the DAG asks for it at run time and maps over it, never copying it.
- When mapping per source/entity, use `expand`, label map indexes (`source.entity`), and cap concurrency against the shared service with a pool.
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
- A task on a dead worker stays `running` until `[scheduler] task_instance_heartbeat_timeout` (300 s by default) before it is retried; the lab lowered it to 120 s because supervisors heartbeat every few seconds (on Composer, set it as an Airflow configuration override).
- Give every task that runs on a worker `retries ≥ 1`: a scale-in, drain, or OOM that outlasts the worker's grace period kills the task, and the scheduler only fails it at the heartbeat timeout; Composer documents the same for removed workers. Bad input still fails at once through `AirflowFailException`, and a DAG test that asserts retries on every business task keeps the rule from eroding.
- Inject faults before any side effect, and for a "retry then succeed" drill inject 100% failure, then lift it mid-retries; a fractional rate over many requests makes the outcome random.
- A time-boxed service (`MAX_RUN_TIME` + `next_url`) needs a server built for long requests: gunicorn's default sync workers are killed at its 30 s worker timeout (an HTML 500 the hook classifies as retryable, so every retry dies the same way), and when all are busy they starve `/healthz` until the kubelet restarts the pod. Run threaded workers (`--worker-class gthread --threads N`, the usual gunicorn setup on Cloud Run) and keep the budget well under both the caller's read timeout and the platform's request timeout (D34).
- Resume a large file by chunk keyed on its `etag`, with the chunk's rows and its ledger row in one transaction: a retry then redoes at most the chunk in flight, and a republished file restarts instead of mixing versions; send `If-Match: <etag>` on every ranged read so a mid-read republish fails loudly (D34).
- Expect the first retry after a clear to wait `max_retry_delay`: exponential backoff is `retry_delay × 2^(try_number − 1)`, and `try_number` keeps counting across clears, so a task cleared twice already backs off at the cap (5 minutes on the lab's extract) on its first new failure.
- Classify a CDN 403 by its `Server` header, not its body: a `HEAD` has no body, S3 behind CloudFront answers `AmazonS3` for a missing key (not published, non-retryable), and CloudFront's own rate-limit block answers `CloudFront` (retryable after a pause).

## Events and file arrival

- Exactly-once comes from idempotency, never from delivery: Pub/Sub delivers at least once.
- Derive the run id deterministically from `(bucket, object, generation)` plus a short hash of the exact object name; Airflow then rejects a redelivery with 409.
- Ack an event after Airflow accepted (2xx), recognised (409), or permanently rejected (other 4xx) it; nack on 5xx, network errors, and 404 (the DAG may not be parsed yet).
- Back the run-id dedupe with a durable file-load ledger keyed by object generation: check it first, short-circuit if loaded, and write it as the last task.
- Read exactly the event's object generation; on a non-versioned bucket an overwritten generation is gone (404), so the run should skip, not fail, because the newer generation has its own event.
- Never let an older generation's load overwrite a newer one: guard the loader with a per-object lock and a max-generation check.
- Derive a file run's processing interval from a validated pattern in the object name, so its readiness record lines up with scheduled consumers.
- A GCS notification publisher never creates its topic, and a publish to a missing topic drops the event silently; monitor the topic and the GCS service agent's publish permission.
- Make the event adapter exit when its streaming pull dies, so its platform restarts it, and run one instance, because the subscription buffers the backlog; on GKE give it a `Recreate` rollout, and on Composer, which runs no custom workloads, host it outside the environment (for example on Cloud Run).
- An adapter outage delays runs but loses nothing while messages stay within subscription retention; replay lost events by republishing the notification for the object's live generation.
- `AssetWatcher` with the Pub/Sub `MessageQueueTrigger` turns one pull into one asset event and one run (three messages became one run), acks on pull before any run exists, and has no routing or dedupe key; prefer an adapter when you need one run per file.
- The provider's Pub/Sub trigger runs on the triggerer and resolves Google credentials before building its client, so give the triggerer the connection and environment it needs.
- Keep event dedupe in the warehouse, not in Airflow's run ids alone: after a metadata restore a redelivered event re-creates its run under the same deterministic id, and only the durable file ledger stops a second load.

## Cross-pipeline readiness

- Keep readiness in a durable warehouse ledger (product, interval, watermark, run id, status), not in Airflow metadata; Assets live in one deployment and carry no interval or watermark.
- Write readiness as an UPSERT on `(product, interval_start, interval_end)`, so a re-run rewrites the same row.
- Publish one readiness product per layer plus one for the whole run, so a consumer waits for exactly the layer it reads.
- Consumers know only ledger product names, never producer DAG ids, so a producer can move to another environment or tool unchanged.
- Wait with a deferrable sensor: check once on the worker, then defer to a trigger that polls the ledger from the triggerer; the waiting task holds no worker slot.
- In a custom trigger, wrap the synchronous hook query in `sync_to_async`, serialise only plain values (ISO timestamps), and ship the trigger's module where the triggerer imports it (the image on GKE; the plugins folder or a PyPI package on Composer).
- Bound every cross-pipeline wait with a sensor timeout, and expect scheduled consumers to time out on intervals whose producers never ran.
- Expect a triggerer outage to pause deferred waits, not fail them: another triggerer claims a trigger at once after a clean stop but only once the dead one's heartbeat is `triggerer_health_check_threshold` (30 s) old after a crash, and the outage counts against the sensor timeout, which is fixed when the task defers.
- Alert on the triggerer's heartbeat, not on task failures: a wait whose upstream turned ready during a triggerer outage sits `deferred` and fails nothing until its timeout.
- Run at least two triggerers (Composer's highly resilient mode does): a lost triggerer's triggers move to the survivor once its heartbeat is 30 s stale (23–24 s after a hang or crash in the lab), instead of waiting for a replacement; after a crash, the survivor and the restarted container race for them, and each trigger still moves only once.
- Let every readiness row name the run that wrote it as `(dag_id, run_id)`, not `run_id` alone: run ids are unique only per DAG, and that pair is what lets you tell Airflow's history from the warehouse's after a metadata restore.

## Helm chart and Kubernetes

- Run the chart's migration and create-user Jobs without Helm hooks when installing with `--wait`: with hooks, Helm waits for pods that wait for the migration hook, a deadlock.
- Jobs are immutable: delete finished chart Jobs before each upgrade and use `--wait-for-jobs`.
- `airflow db migrate` only moves forward: a `helm rollback` restores manifests, not the schema.
- A `helm rollback` creates a new revision number; read the history, do not expect the old number back.
- Preview every upgrade with `helm diff`, and test the rollout path by changing a value that feeds the chart's config checksum.
- Use the chart's renamed worker keys (`workers.celery.*`); the old ones only warn.
- Lower the Celery workers' `terminationGracePeriodSeconds` from the chart's 600 s when tasks are short; one stuck pod otherwise stalls a rollout for ten minutes.
- Ship task logs to object storage before making workers a Deployment: the API server streams a running task's log from its worker by hostname, and a finished task's log otherwise dies with the pod (scale-in, drain, OOM).
- With Deployment workers, report the pod IP as the worker hostname (`hostname_callable = airflow.utils.net.get_host_ip_address`); a Deployment pod's name does not resolve.
- Keep every generated secret (fernet, JWT, API secret, connections) in Kubernetes Secrets created once by the deploy script and never rotated by a re-run; a rotated JWT secret breaks running tasks.
- Changing a Secret consumed through `envFrom` does not roll pods; restart the workloads, or hash the Secret into a pod annotation.
- Treat image tags as immutable and bump them on every change, across every manifest and default that names the image; with `IfNotPresent`, a same-tag rebuild never reaches running pods.
- Enable PgBouncer in front of an external metadata DB, and keep the bundled Postgres subchart off.
- [GKE] Run two schedulers and two triggerers, each behind a PodDisruptionBudget of `maxUnavailable: 1`: the scheduler HA needs only row locks inside a transaction, which PgBouncer's transaction pooling carries (no lock errors, no task run twice when one was SIGKILLed mid-run), and Composer recommends two schedulers. The scheduler's startup probe keeps a new pod un-Ready until its job heartbeats, so its PDB guards real capacity; the chart's triggerer has none, so check live triggerers, not Ready pods, during a drain.
- [GKE] A crashed scheduler's queued tasks still run (their Celery messages are already in the broker), and its job row stays `running` until a surviving scheduler's orphan check (`orphaned_tasks_check_interval`, 300 s) marks it failed and adopts its task instances.
- Run PgBouncer with two replicas, preferred (not required) anti-affinity, and a PodDisruptionBudget of `maxUnavailable: 1`: a single replica moved by a drain cuts every component's DB connections, and the scheduler, dag-processor, and triggerer exit instead of reconnecting, while with two no component restarted; leave PodDisruptionBudgets off other single-replica components, or a drain blocks.
- Give workload pods the `restricted` profile: non-root uid, seccomp `RuntimeDefault`, drop ALL, no privilege escalation, read-only root with emptyDirs for scratch, and no service-account token unless they call the API.
- Roll Pod Security out in `warn` mode first, then `enforce`.
- Server libraries may write under `$HOME` (gunicorn's control socket); a non-root, read-only image needs that feature disabled or a writable path.
- Keep workload Deployments at two replicas with `maxUnavailable: 0` and real probes, so a bad image tag or failing probe leaves the old pods serving.
- Give one-shot Jobs a unique name per run, `ttlSecondsAfterFinished`, `backoffLimit`, and `activeDeadlineSeconds`.
- A worker hostname arrives as a pod FQDN; match it by prefix.
- Grant the Airflow worker ServiceAccount a Role only in the namespace where it launches pods, and remember that deleting that namespace deletes the Role too.
- Choose the executor for orchestration throughput and isolation; Celery fits thin HTTP and pod-launch tasks and matches Composer's model.
- A task naming an executor the deployment does not configure is an import error; keep multi-executor experiments in their own DAGs.
- A KubernetesExecutor pod costs seconds of start-up and a DAG re-parse per task; keep it for tasks that need their own memory limit, and know that an OOMKilled pod's log may never reach remote storage.
- Celery's warm shutdown works on Kubernetes: on SIGTERM a worker stops taking tasks and finishes the running ones within `terminationGracePeriodSeconds`; size the grace to typical task length, not the longest, because it also bounds every rollout and drain, and let retries cover the rest.
- [GKE] Behind PgBouncer in transaction pooling, set `max_prepared_statements` (PgBouncer 1.21+) before pointing KEDA's PostgreSQL scaler at it: its pgx statement cache otherwise fails most polls with `prepared statement … already exists`, and the HPA silently freezes the worker count with no pod failing.
- Drill a scale-in deterministically: hold an extra replica by raising the minimum, mark the target pod with `controller.kubernetes.io/pod-deletion-cost: "-100"`, then lower the minimum; the ReplicaSet deletes the cheapest pod.
- With a KEDA minimum above 0 the HPA does the scaling on its own 15 s loop: `cooldownPeriod` is ignored and the HPA scale-down stabilisation window is the setting that keeps workers through gaps.
- KEDA's Celery query counts running and queued task instances, so it scales for a full executor but not for a full pool; starved pool tasks wait in `scheduled`.
- Size requests from observed peaks (`max_over_time(container_memory_working_set_bytes[…])` over real runs and drills, with the busiest dashboards open on their widest ranges), not from chart defaults; the lab's worker peaked above its request, the api-server far below, and Grafana was OOMKilled loading a wide dashboard range.
- Fix a per-request memory spike vertically, not with replicas: one pod serves the request, so extra replicas sit idle while it is OOMKilled; set the limit with headroom above the worst realistic case (Grafana idled near 270 Mi, peaked at 542 Mi on a 7-day range, and holds at a 768 Mi limit).
- [GKE] Set a Redis `socket_timeout` (Airflow `[celery_broker_transport_options]`, e.g. 10 s, above kombu's 1 s BRPOP block): without it, a worker that ran a task through a broker restart can block forever reading a dead socket, stop answering `celery inspect ping`, and lose the task to its liveness probe.
- [GKE] On Celery < 5.7, a prefork worker that ran a task through a broker reconnect queues new tasks behind it while its other slots idle (`AsynPool.flush` clears the busy-process set, celery/celery#10346); backport the fix or move to 5.7, and drill it with a task running, not idle.
- [GKE] Size probes for a CPU-starved node, not an idle laptop: under contention a container gets CPU in proportion to its request, and the chart's exec probes boot the Airflow CLI (~1.8 CPU-seconds), so a 100m triggerer's probe nears its 20 s timeout and a cold start restart-loops. Curl the scheduler's own `/health` server (`enable_health_check`) instead of `airflow jobs check`, give the remaining exec probes `timeoutSeconds` up to their period, and make startup budgets generous; rehearse by capping node CPUs and restarting every Airflow pod at once.
- Measure a data service's memory against its container limit with real files and concurrent requests, not one fixture: a Python service decoding Parquet held 1.33 GiB for one 59 MB month until it streamed batches, Arrow used the system allocator (`ARROW_DEFAULT_MEMORY_POOL=system`; jemalloc kept ~500 MB of freed buffers), and glibc was told to return memory (`MALLOC_ARENA_MAX=2`, a fixed `MALLOC_MMAP_THRESHOLD_`); with one chunk in flight per process, three concurrent months then peaked at 753 MiB in the pod. The same settings apply to the service's Cloud Run container. Profile inside the real image, not a laptop venv, since those allocator settings change the answer; size streaming batches by what they cost after their copies, not by rows (100,000-row CSV parts, copied about four times on the way into `COPY`, cost ~250 MiB per process and brought two real FHVHV chunks to 967 MiB of a 1 GiB limit; 25,000 rows ran as fast and peaked at 530–670 MiB); and refuse up front, as non-retryable, an input whose smallest unit cannot fit (a 451 MiB row group), or every retry is another OOMKill (#90).

## Observability and alerting

- [GKE] Turn on StatsD with InfluxDB-style tags (`statsd_influxdb_enabled`): Airflow 3 emits pool, task-state, and duration metrics with tags only, and plain StatsD collapses every pool into one series.
- [GKE] Read the live exporter's `/metrics` before building dashboards; executor gauges already carry `executor_class_name`, and legacy per-pool names still appear next to the tagged ones.
- [GKE] Give the statsd-exporter a series TTL, or it keeps one series per replaced pod forever (`triggers_running` summed to 8 for 2 triggerers), and restart it when its mappings change.
- [GKE] Alert on a StatsD counter's new series, not only on its `increase()`: the statsd-exporter creates the counter at 1 on its first increment and drops it after its TTL, and `increase()` needs two samples, so a one-off task failure never fired `sum(increase(airflow_ti_failures[10m])) > 0`; add `or count(airflow_ti_failures unless airflow_ti_failures offset 10m) > 0`.
- Alert on a heartbeat's rate and on its series going missing: a stopped component leaves its counter frozen, and an exporter restart drops the series entirely (in PromQL, `or vector(0)`).
- Simulate a crash as a sustained outage (scale to 0) when asserting an alert; a killed pod returns faster than any `for:` window.
- [GKE] With more than one replica, alert on fewer live replicas than desired, not only on a missing heartbeat: Airflow's heartbeat counters carry no hostname and sum over replicas, so losing one of two never reaches 0, and Deployment availability misses a hung process whose pod stays Running. Count `running` job rows with a heartbeat under 30 s in the metadata DB (a SQL exporter beside it) against the desired replicas.
- [GKE] Drill a hung component with SIGSTOP on its process: the pod stays Running and Ready, only the job heartbeat stops, and the liveness probe (`airflow jobs check`, 5 x 60 s) takes about 5 minutes to restart it; deleting the hung pod waits out its full grace period, because a stopped process cannot act on SIGTERM.
- [GKE] Drill a crash by SIGKILLing the component's process inside its container, not with `kubectl delete pod --force --grace-period=0`: the kubelet still sends SIGTERM, the component exits cleanly, and crash-only behaviour (a triggerer's 30 s wait before taking over a dead one's triggers) never runs.
- Do not read component health off `/api/v2/monitor/health` alone after a crash: it reports the newest heartbeat among jobs still marked `running`, and a crashed scheduler or triggerer leaves its job row `running` forever.
- [GKE] Schedule `airflow db clean` with the chart's `databaseCleanup` CronJob (it covers `job`, `log`, `task_instance`, `trigger`, `xcom`, and more, deleting `job` rows by heartbeat age, so live components are safe): crashed components' job rows and all run history otherwise grow without bound; `--skip-archive`, or the `_airflow_deleted__*` tables grow instead.
- [GKE] Gate a CronJob that needs the metadata DB on `airflow db check --retry N --retry-delay S` before its real command: the chart's cleanup Job has `backoffLimit: 1` and no wait, so a run that starts during a Cloud SQL maintenance window or failover fails at once.
- [GKE] Replace kube-prometheus-stack's `KubeJobFailed` for CronJobs: it fires while any failed Job object exists, and `failedJobsHistoryLimit` keeps the last failed one after later runs succeed, so one bad night pins the alert until someone deletes the Job; suppress a CronJob's failed Job once `kube_cronjob_status_last_successful_time` is newer than the Job's start (joined through `kube_job_owner`).
- [Composer] Use Composer 3's database retention policy (on by default, 60 days, runs at least daily) instead of a cleanup DAG: Google calls the maintenance DAG obsolete on Gen 3, and Composer 3 workers cannot reach the metadata DB anyway.
- [GKE] Watch the metadata DB from outside the cluster (Cloud SQL monitoring, or `pg_up`): PgBouncer keeps accepting clients while the server is gone, so no probe fails first.
- [GKE] Detect a stuck rollout by pods above the spec (`status.replicas > spec.replicas`), not by availability or updated replicas: the old pods keep serving, and a crash-looping new pod counts as updated.
- [GKE] Detect a failing chart migration from its pod's restarts: the Job uses `restartPolicy: OnFailure`, so `kube_job_status_failed` stays 0 until the backoff limit.
- Back-test every new alert expression with a range query over the incident you already have, before waiting for the next one.
- [GKE] Alert on the autoscaler's own failed-poll counter (KEDA: `keda_scaled_object_errors_total`): a failing scaler freezes the replica count with no pod failing, the HPA's `ScalingActive` condition flips back on every good poll, and KEDA's per-trigger `keda_scaler_detail_errors_total` stayed at 0 through a real outage.
- [GKE] Give Prometheus a persistent volume (`storageSpec`; a PD-backed PVC on GKE, or Managed Service for Prometheus): on the operator's default emptyDir, one node drain wiped the history the alert back-tests needed, and `retention` alone promises nothing across a pod move.
- When every rule group misses evaluations at the same moment while each evaluation stays fast, check the node's clocks before tuning intervals: Prometheus counts missed slots on the wall clock, so a stepped clock fakes the misses.
- [GKE] Keep a component's ServiceMonitor with the monitoring manifests, not behind a "monitoring CRDs exist" switch in its own chart; that switch made deploy order silently decide whether KEDA was scraped.
- [GKE] Alert on task instances sitting in `queued` for minutes (`airflow_pool_queued_slots`): a broker restart drops the Celery message but not the task's state, and the scheduler only requeues it after `task_queued_timeout` (600 s), silently; lowering that timeout instead turns capacity waits into failures, because the third stuck attempt fails the task.
- [GKE] When `KubeAPIErrorBudgetBurn` fires, split the burn into 5xx and slow requests before blaming errors: the apiserver SLO counts a write slower than 1 s (and a read slower than 1, 5, or 30 s by scope) as an error, and on the lab slow lease renewals were ~70% of the burn against ~6% for 5xx. Then compare `apiserver_request_sli_duration_seconds` with `etcd_request_duration_seconds` to see whether the time is spent in etcd.
- [Composer] Alert on each data product's freshness, not only on the platform: compare the end of its newest ready interval with a per-product deadline kept beside the readiness table (on GCP, a Cloud Monitoring alert over the BigQuery table), so a paused DAG or a run the scheduler never creates still fires. Airflow's Deadline Alerts cannot: a deadline is created with a DAG run, so no run means no deadline to miss.
- Measure a product's freshness by its data interval's end, not by when its readiness row was written: re-running an old interval rewrites the row and would make a stale product look fresh.
- [GKE] Roll an exporter whenever its config changes (a checksum annotation on the pod template, or a reloader): `sql_exporter` and most exporters read their collectors only at start, and neither a ConfigMap update nor `docker compose up` restarts them, so a new collector exports nothing and its alert can never fire, with no error anywhere.

## Upgrades and rollback

- Back up the metadata DB before every Airflow minor upgrade (on Composer, save an environment snapshot); the way back is restore plus redeploy of the old line, never a manifest rollback alone.
- [GKE] A `helm rollback` onto a migrated schema never lands: the old migration Job fails with `Can't locate revision identified by '<new head>'`, new pods wait in their `wait-for-airflow-migrations` init container, and the old pods keep serving the new version.
- [GKE] Rehearse an upgrade on a throwaway database (`data.metadataConnection.db`) on the same server, never on the only copy.
- [GKE] Stop Airflow and PgBouncer before a release that points PgBouncer at another database: PgBouncer rolls while the migration Job runs, so the Job migrates whichever database an old PgBouncer pod still serves and can report success on the wrong one.
- The older Airflow line needs its own provider pins (Composer publishes one list per build); a seam module that uses a newer provider API breaks on it, so test imports on both images before the roll.
- [Composer] Treat a Cloud SQL restore or a Composer snapshot load as data drift, not only a rollback: Airflow forgets every run after the backup while the warehouse keeps their rows, and nothing else alerts; match the ledger's `(dag_id, run_id)` against Airflow's runs (a SQL exporter on each side, joined in PromQL) and alert on the difference.
- After a metadata restore, replay the lost runs one at a time in the order they finished, manual and event runs under their own ids; replayed together, a consumer starts at once on its producers' still-`ready` ledger rows and builds before they are rebuilt.
- Expect the scheduler not to backfill a restore's gap with `catchup=False`: it re-creates only the latest interval's run, so every earlier lost scheduled run needs an explicit replay (as a manual run: its `scheduled__` id belongs to the scheduler).

## Shipping DAGs and images

- Ship DAG files and the shared package they import as one versioned unit: a DAG folder that syncs ahead of the image (or Composer's `dags/` ahead of its plugins or PyPI packages) produces import errors on every component.
- Never edit DAGs in a live-synced location while a run or check depends on it.
- [GKE] Sync both DAGs and the shared package with git-sync from one ref with a read-only deploy key and pinned host keys, and have checks refuse to run when the local tree differs from the served commit.
- [GKE] Alert on git-sync's own counters (`git_sync_count_total` by status, served with `GITSYNC_HTTP_METRICS`): a failing fetch keeps every sidecar Ready on its last good commit, so DAGs go stale without any pod-level alert.
- [Composer] Composer copies DAGs from its bucket instead of git-sync; before relying on it, find out how a stalled bucket sync shows up there, because healthy pods prove nothing about DAG freshness.
- Run a DagBag import test in CI on every push; it catches the import errors that would otherwise surface on every component after a sync.
- A DAG whose file vanished still answers `GET /dags/<id>` with `is_stale: true`, but triggering it returns 404; check `is_stale` before you trigger, and alert on it.
- Check import health from the DAG processor (`airflow dags list-import-errors`), not only from the UI.
- Make deploy scripts idempotent: create pools and connections on every run.
- [GKE] Never rebuild an image under a tag that already ran: nodes cache by tag (`imagePullPolicy: IfNotPresent`), so pods keep the old contents without any error. Bump the tag on every content change, including a shared package baked into the image; on the lab the seam changed twice without a bump and a local-delivery deploy could not import `tlc_monthly` (#92).
- Give each image tag exactly one source that the deploy reads (Kustomize `images:`, a Helm `--set`, an Airflow Variable): a tag repeated across a Makefile, manifests and a code default lets a bump push the new image and deploy the old one.
- [Composer] Keep the dbt image with the Cloud Run Job definition, deployed with the image; the DAG names only the Job, so a dbt release never needs a DAG change.
- Use `postgresql://` in connection URIs (Airflow normalises it), and pass JSON-form connections when extras are needed.
- Keep lab-default credentials out of real environments (the Helm chart's create-user Job gives `admin`/`admin`), and give an event adapter its own API identity.
- Keep emulator switches (`STORAGE_EMULATOR_HOST`, `PUBSUB_EMULATOR_HOST`) out of real manifests: they switch clients to anonymous credentials or insecure channels.

## Warehouse and dbt

- Create every landing table at service startup (best effort) and again before each load, so dbt sources resolve on a fresh warehouse before the first extract.
- Load the warehouse from the staged object, not from in-memory rows, to mirror a GCS-to-BigQuery load.
- Keep file-sourced tables keyed by object and generation, not by run interval.
- Expect late-arriving parents when parent and child are extracted per interval (a booking names a lead from three weeks before): a fresh warehouse holds children whose parent was never loaded, so a strict relationship test fails every run, a backfill included; decide per pipeline between a parent lookback and a warning with an `unknown` bucket (#136: the lab warns).
- Dedupe silver with a deterministic order (latest `_loaded_at`, then a tie-breaker) so re-landed rows resolve the same way every time.
- Keep dbt SQL portable to BigQuery, and mark each dialect-specific line with a comment naming the BigQuery form.
- Run `dbt parse` in the image build as a smoke check, and drive connection settings from env vars so one image serves every environment.
- An intermittent "dbt was unable to infer all dependencies" failure was seen and never reproduced; give dbt tasks retries and avoid concurrent builds against the same target.
- On Postgres, dbt's table materialization drops the old table with `CASCADE`, which deletes every view on it, including another pipeline's (issue #27); BigQuery has no such dependency, so check cross-pipeline views after any rebuild on a Postgres stand-in.
- For files republished whole (TLC months), replace a partition per build (`insert_overwrite` on the month; `delete+insert` on the stand-in) from the latest *completed* file version only, so a republish swaps its month and a half-loaded version stays invisible; reconcile bronze = silver + quarantine per month.
- Retire old months before loading the new one, and tell each workload which months to keep, never which to drop: a retry then converges, a backfill of an old month cannot retire the newest ones, and the months a concurrent catch-up run is still loading count as held. On BigQuery this is partition expiration (or a `DELETE` on the partition column) on month-partitioned tables; a Postgres `DELETE` only frees space for reuse, so size plateaus instead of falling (D35, #87).
- Pass a run's dbt vars (the data month) as one `--vars <json>` argument built from templated operator args; on a Cloud Run Job the same list goes into the execution's container-override args.
- Scope a pipeline's semantic-layer gate to the domains it waited for: MetricFlow's `mf validate-configs` queries every semantic model on the warehouse, so on the first deploy of a new domain it fails every other pipeline until that domain's first load (#168); validate the whole manifest offline and query only the waited-for pipelines' models.

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
- Drill a stateful dependency in every state it can hold work in, not only idle: one Redis restart was harmless with no work, lost a task that was waiting in it, and stalled a worker that was running one.
- [GKE] A port-forward binds to one pod and exits when that pod's container stops; restart it after every rollout or restart.
- Fetch a mapped task's logs with `?map_index=` on the task path, not the index in the path.
- Re-run a verification script after any edit to it, and verify a delegated agent's report against the raw logs before relying on it.
- Distrust a reassuring zero from a check's diagnostics: a broken restart counter reported no restarts for a DB outage that restarted three components.

## Process

- Record a decision with its rationale in the plan before building on it, and change the plan before changing course.
- Keep project instructions to invariants; versions and status belong in the plan and the work log.
- Surface genuine forks (event adapter vs AssetWatcher) to the owner instead of deciding silently; a spike built side by side settled it with evidence.
- Treat identity, IAM, Workload Identity, and private networking as their own workstream on real GCP; the lab deferred them on purpose.
- Give automation on a real project no role that can enable APIs, change IAM or quotas or buy capacity, and check its permissions with `testIamPermissions`: IAM changes take minutes to apply, so testing a fence by attempting the forbidden action can do it (an agent enabled the Compute Engine API on the lab project that way).
