# Runbook

Operational entries for the lab, grown phase by phase.
Every command uses the `kind-pplk8s` context and the `workloads` namespace; `K` below stands for `kubectl --context kind-pplk8s -n workloads`.

## Phase 2 drills

Each drill breaks the healthy EL Factory Deployment on purpose, using a `kubectl patch` or `kubectl set image` against the live object.
The symptoms below were observed on Kubernetes 1.36.4 (kind) with the manifests in `platform/k8s/workloads/`.
Every drill is undone the same way: re-apply the manifests with `platform/k8s/workloads-up.sh`, which restores the declared state.
(`kubectl rollout undo` also works, but it returns to the previous revision, which is the broken one if you drilled twice in a row.)

General triage order for any pod problem:

```bash
K="kubectl --context kind-pplk8s -n workloads"
$K get pods -o wide                          # STATUS column names the failure class
$K describe pod <pod>                        # State / Last State / Events at the bottom
$K logs <pod> [--previous]                   # --previous reads the last crashed container
$K get events --sort-by=.lastTimestamp       # namespace-wide timeline
```

One property shows up in every drill: the Deployment uses `maxUnavailable: 0`, so a bad rollout leaves the two old pods Running and serving the Service while the new pod fails.
`kubectl rollout status` then times out instead of the service going down.

### 1. Bad image tag (ImagePullBackOff)

Trigger:

```bash
$K set image deployment/el-factory el-factory=localhost:5001/el-factory:9.9.9
```

Symptom: the new pod's STATUS goes `ErrImagePull`, then `ImagePullBackOff`.
`kubectl rollout status` stalls with `Waiting for deployment "el-factory" rollout to finish: 1 out of 2 new replicas have been updated...` and then times out.
The two old pods stay `1/1 Running`.

Diagnosis (`describe pod` events):

```
Normal   Pulling  kubelet  Pulling image "localhost:5001/el-factory:9.9.9"
Warning  Failed   kubelet  Failed to pull image "localhost:5001/el-factory:9.9.9": rpc error: code = NotFound desc = failed to pull and unpack image "localhost:5001/el-factory:9.9.9": failed to resolve reference "localhost:5001/el-factory:9.9.9": localhost:5001/el-factory:9.9.9: not found
Warning  Failed   kubelet  Error: ErrImagePull
Normal   BackOff  kubelet  Back-off pulling image "localhost:5001/el-factory:9.9.9"
Warning  Failed   kubelet  Error: ImagePullBackOff
```

`not found` means the registry answered but has no such tag.
A connection error instead would point at the registry or the node's containerd mirror config.
Check what the registry holds with `curl -s localhost:5001/v2/el-factory/tags/list`.

Fix: use a tag that exists (`make push` publishes `ELF_IMAGE`, see `make -s print-ELF_IMAGE`), then `workloads-up.sh`.

### 2. Failing probe

Two variants, which behave differently.

**Readiness probe fails** (the app is fine, the probe asks the wrong question):

```bash
$K patch deployment el-factory --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/nope"}]'
```

Symptom: the new pod stays `0/1 Running` with `RESTARTS 0`, and the Deployment shows `READY 2/2  UP-TO-DATE 1` because the old pods still serve.
The Service's EndpointSlice lists the new pod's address with `ready=false`, so it receives no traffic.

```
Warning  Unhealthy  kubelet  Readiness probe failed: HTTP probe failed with statuscode: 404
```

The probe line in `describe pod` shows the cause: `Readiness: http-get http://:http/nope ...`.
Readiness never restarts a container; it only gates traffic.

**Startup (or liveness) probe fails** (the kubelet kills the container):

```bash
$K patch deployment el-factory --type=json -p '[
  {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/nope"},
  {"op":"replace","path":"/spec/template/spec/containers/0/startupProbe/httpGet/path","value":"/nope"},
  {"op":"replace","path":"/spec/template/spec/containers/0/startupProbe/failureThreshold","value":3}]'
```

Symptom: the new pod climbs through `RESTARTS 1, 2, ...` and ends in `CrashLoopBackOff`.

```
Warning  Unhealthy  kubelet  Startup probe failed: HTTP probe failed with statuscode: 404
Normal   Killing    kubelet  Container el-factory failed startup probe, will be restarted
Warning  BackOff    kubelet  Back-off restarting failed container el-factory in pod ...
```

`kubectl logs` shows the probe's requests in the gunicorn access log (`GET /nope ... 404 ... "kube-probe/1.36"`), then `Handling signal: term` when the kubelet stops it.
Telltale difference from a real crash: the app log is healthy and ends with a SIGTERM, and the exit is a kill, not an error.

Fix: restore the probe path with `workloads-up.sh`.

### 3. OOMKill (memory limit too tight)

Trigger (requests must not exceed limits, or the API rejects the patch with `resources.requests: Invalid value: "128Mi": must be less than or equal to memory limit of 20Mi`):

```bash
$K patch deployment el-factory --type=json -p '[
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"20Mi"},
  {"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"16Mi"}]'
```

Symptom: the new pod restarts within a second of each start and ends in `CrashLoopBackOff`.
`describe pod` is the diagnosing command:

```
State:          Waiting
  Reason:       CrashLoopBackOff
Last State:     Terminated
  Reason:       OOMKilled
  Exit Code:    137
Limits:
  memory:  20Mi
```

Exit code 137 is 128 + SIGKILL(9); the reason `OOMKilled` says the kernel's cgroup killed it for exceeding the limit.
`kubectl logs --previous` shows only the gunicorn start-up lines (`Starting gunicorn`, `Listening at`) and then nothing: the process is killed with no error message, which is why logs alone mislead.
Also visible: `Startup probe failed: ... connection refused`, because the app never finishes starting.
`kubectl get pod <pod> -o jsonpath='{.status.containerStatuses[0].lastState.terminated}'` returns `"reason":"OOMKilled","exitCode":137`.

Fix: raise the limit (the manifest says 256Mi) by re-applying with `workloads-up.sh`.
Size the limit from observed usage; the lab has no metrics-server, so raise it step by step.

### 4. Missing Secret (CreateContainerConfigError)

Trigger (a typo in the Secret name, the common real-world cause):

```bash
$K patch deployment el-factory --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/envFrom/1/secretRef/name","value":"warehouse-credential"}]'
```

Symptom: the new pod's STATUS is `CreateContainerConfigError` with `RESTARTS 0`; the container is never created, so there are no logs at all.

```
State:          Waiting
  Reason:       CreateContainerConfigError
Warning  Failed  kubelet  Error: secret "warehouse-credential" not found
```

The image pull succeeded (`Pulled` events repeat), and the kubelet then fails resolving `envFrom`.
Diagnosis commands: `$K describe pod <pod>` for the exact missing name, then `$K get secret` to compare with what exists (`warehouse-credentials`, 6 keys).
`kubectl logs` has nothing to show because the container was never created.

Fix: correct the reference, or create the Secret; the kubelet retries on its own and the pod starts without a restart of the Deployment.
Here, `workloads-up.sh` restores both the Secret and the reference.
The same error appears for a missing ConfigMap or a missing key referenced through `secretKeyRef`.

### Restoring the healthy state

```bash
platform/k8s/workloads-up.sh
$K get pods -l app.kubernetes.io/name=el-factory     # 2 pods, 1/1 Running
make phase2-check
```

## Phase 4 drills

Both drills are automated in `tests/e2e/phase4-check.sh` (`make phase4-check`); the observations below come from its first full pass on 2026-10-10.
The script restores the EL Factory ConfigMap and the DAG's paused flag on exit, even when it fails.

### 1. Kill a mapped extract task mid-run

Trigger: set `PAGE_SIZE=1` in ConfigMap `el-factory-config` and roll EL Factory, so `synthetic.customers` spans 200 pages.
Trigger a `sales_elt` run, wait until `extract` map index 0 is `running`, then force-delete the Celery worker pod running it (`kubectl -n airflow delete pod airflow-worker-N --force --grace-period=0`).

Observed:

- The task instance kept reporting `running` for about 5 minutes after the pod died.
  Airflow notices a dead worker only through the task-instance heartbeat timeout, not through the pod deletion.
- Then the task went to `up_for_retry` on try 1, to `running` on try 2 about 20 seconds later, and to `success` on try 2.
- The tries API records the killed try as `failed`.
- Row counts stayed at 200 customers and 40 orders for the run, and the gold and exposed table hashes did not change.
  Try 2 restarts the entity at page 0, and page 0 clears the whole `(run_id, interval)` before loading, so the retry duplicates nothing.

Diagnosis: `GET /api/v2/dags/sales_elt/dagRuns/<run>/taskInstances/extract/0/tries` shows each try with its state and hostname; `kubectl -n airflow get pods` shows the replacement worker.

Recovery: none needed; the task retry is the recovery.
To shorten detection, lower the task-instance heartbeat timeout (`[scheduler] task_instance_heartbeat_timeout`), at the cost of more false positives under load.

### 2. Transient EL Factory failures (`FAIL_RATE`)

Trigger: set `FAIL_RATE=1` in ConfigMap `el-factory-config` and roll EL Factory, trigger a run, let the first attempts fail, then set `FAIL_RATE=0` and roll again.
`FAIL_RATE=1` is used instead of a fraction because a fraction across many pages makes the outcome random.

Observed:

- Try 1 of each extract failed with `POST /extract: HTTP 503: injected transient failure (FAIL_RATE)`.
  The hook raised `ElFactoryTransientError`, so Airflow scheduled a retry with exponential backoff instead of failing the task.
- After the failure rate went back to 0, both extract map indexes succeeded on try 3 and the run succeeded.
- Row counts and the gold and exposed hashes did not change.

A non-retryable error (`retryable: false`, 4xx, 502) raises `AirflowFailException` instead and fails the task at once, without spending retries.

### 3. Clearing a dbt stage alone drops its downstream views

Clearing only `dbt_gold` re-runs `dbt build --select gold`, which recreates the gold tables and drops the dependent exposed views (`DROP ... CASCADE`), without rebuilding them.
Clear a dbt stage together with its downstream tasks (`include_downstream`), as the check does.

### 4. DAGs go stale after a Docker Desktop restart

Symptom: after a reboot or a Docker Desktop restart, triggering a DAG returns `404 Dag with dag_id: '<id>' not found`, while `GET /api/v2/dags/<id>` still answers with `is_stale: true`.
The dag-processor log shows an empty file table.
Seen on 2026-10-10: `make phase4-check` failed with `could not trigger sales_elt`.

Diagnosis: `docker exec pplk8s-worker ls /mnt/pplk8s/dags` is empty and `grep pplk8s /proc/mounts` inside the node shows a `tmpfs` instead of the bind mount.
Docker started the kind node containers before the WSL file share was ready, so the `extraMounts` bind of `airflow/dags` resolved to nothing.

Recovery: `docker restart pplk8s-worker pplk8s-worker2` re-resolves the bind; the dag-processor re-parses within a minute.
`platform/kind/ensure-dag-mount.sh` does this automatically and runs from `make airflow-up`; the e2e checks wait for `is_stale=false` (`wait_dag_ready`) before triggering.
The failure mode disappears with git-sync delivery (D10, Phase 6).

### A local DAG deploy from another clone

Symptom: `make airflow-up` with `DAG_DELIVERY=local` stops with `the kind workers mount another clone's DAGs`.
Seen on 2026-10-31 (#173), before the check existed: a deploy from a second clone ran that clone's image with the first clone's DAGs and failed with `TypeError: validate_semantic_layer() missing 1 required keyword-only argument`.

Diagnosis: `cluster-up.sh` writes the absolute path of the clone that created the cluster into the workers' `extraMounts`, once, so the cluster serves that clone's `airflow/dags` whichever clone runs `make`.
`ensure-dag-mount.sh` compares a digest of the workers' DAG files with this checkout's and names both paths.

Recovery: run `make` from the clone the message names, or recreate the cluster from this one (`make cluster-down cluster-up`).

## Phase 5 drills

The event path is explained in [`events.md`](events.md); `tests/e2e/phase5-check.sh` (`make phase5-check`) automates the dedupe cases.
The drills below were run by hand on 2026-10-10.

### 1. The Pub/Sub emulator restarts and loses its topology

Trigger: `docker restart pplk8s-pubsub-1`, then upload a file to `gs://landing/returns/`.

Observed:

- The emulator keeps topics and subscriptions in memory, so after the restart `GET /v1/projects/pplk8s/topics/gcs-object-events` answers 404.
- The upload still succeeds, and its event is lost: fake-gcs logs `error publishing event: rpc error: code = NotFound desc = Topic not found` at INFO level and carries on.
- The event adapter's streaming pull fails with `404 Subscription does not exist (resource=file-arrivals)`; the process exits and the kubelet restarts the pod (`restartCount` 1).

Diagnosis: `docker logs pplk8s-gcs-1 | grep 'error publishing'`, `kubectl -n workloads get pods` (restarts), `kubectl -n workloads logs deploy/event-adapter --previous`.

Recovery: `make services-up` re-runs `pubsub-init`, which recreates the topic and both subscriptions; the restarted adapter subscribes again.
Events published while the topic was missing are gone; replay each by publishing the notification for the object's live generation (attributes `bucketId`, `objectId`, `objectGeneration`, `eventType=OBJECT_FINALIZE`) to `POST http://localhost:8085/v1/projects/pplk8s/topics/gcs-object-events:publish`, or by re-uploading the file.
A replay is safe by construction (D18).
On real GCP the notification config and topic are durable, so this failure mode belongs to the emulator; the equivalent production risk is a deleted topic or a missing publisher permission on the GCS service agent.

### 2. The adapter is down while files land

Observed when the adapter was first deployed: two events published before it existed waited in subscription `file-arrivals` and were handled within a second of the pod starting (one `ignored`, one `triggered`).
Pub/Sub keeps unacked messages for the subscription's retention period, so an adapter outage delays runs but loses nothing.

Recovery: none beyond bringing the adapter back; its Deployment uses `Recreate`, so a rollout never runs two subscribers.

### 3. A poison event

Trigger: upload a routed object whose name breaks the DAG's contract, such as `returns/not-a-day.jsonl`.

Observed: the adapter triggers a run (routing looks only at the prefix); `validate_event` raises `AirflowFailException` and the run fails on try 1 without spending retries.
Nothing reaches EL Factory or the warehouse.

Recovery: fix or delete the object; a corrected upload is a new generation with its own event and run.

## Phase 6 drills

Every drill is detected by a Prometheus alert (`platform/monitoring/manifests/airflow-rules.yaml`, PLAN.md D28) and shows on Grafana's "Airflow overview" dashboard (`make grafana-ui`).
Drills 1–4, 7–9, 11, and 12 are automated in `tests/e2e/phase6-check.sh` (`make phase6-check`; `DRILLS="1 9"` runs a subset): inject, wait for the alert to fire, run the recovery below, wait for it to resolve, then run the `hello` canary on a Celery worker.
Drill 5 reinstalls Airflow and lives in `tests/e2e/phase6-upgrade-drill.sh` (`make phase6-upgrade-drill`).
Drill 6 is part of the KEDA check, `tests/e2e/keda-check.sh`, which `make phase6-check` runs first.
Drill 10 restores the lab's own metadata DB and lives in `tests/e2e/metadata-restore-drill.sh` (`make metadata-restore-drill`, also in `make phase6-check`).
Times below are from the passes on 2026-10-10; Prometheus scrapes and evaluates rules every 15 s, so each detection time includes up to one interval on top of the rule's `for:`.
`KA` stands for `kubectl --context kind-pplk8s -n airflow`.

### 1. Lose a scheduler

Two schedulers run (D31), each its own `SchedulerJob`; they share the work through row locks, and either can schedule any DAG run.
Three variants, from mildest:

- 1a crash: SIGKILL one scheduler's `airflow scheduler` process during a 16-task `ops_load_test` run (the image has no `kill`: `KA exec <pod> -c scheduler -- python -c 'import os, signal; os.kill(<pid>, signal.SIGKILL)'`; the job is the lowest-numbered `airflow scheduler` process, PID 1 is dumb-init).
- 1b hang: SIGSTOP one scheduler's process instead; the pod stays Running and stops heartbeating, which a crash never shows long enough to alert on.
- 1c outage: `KA scale deploy/airflow-scheduler --replicas=0`.
  Deleting a pod is not a useful drill: the Deployment replaces it within seconds, faster than any alert window.

Observed (2026-10-12, two schedulers):

- Crash (1a): the 12 queued tasks reached a worker anyway, because the Celery messages were already in Redis; the run succeeded 80–83 s after the kill with every task instance on try 1 and no `task_instance_history` rows, so nothing ran twice.
  The container restarted in place and its new job heartbeated within about 10 s.
  The dead job's row stayed `running` until the other scheduler's periodic orphan check (`[scheduler] orphaned_tasks_check_interval`, 300 s) logged `Marked 1 SchedulerJob instances as failed`, about 4 minutes after the kill; that check also adopts the dead job's queued and running task instances.
  No alert fires, by design: the role never stopped.
- Hang (1b): `AirflowSchedulerDegraded` fired after 170 s (30 s to go stale, then the rule's 2 minutes), with `AirflowSchedulerDown` and `AirflowComponentUnavailable` quiet, because the survivor kept the summed heartbeat up and the hung pod counted as available.
  The canary succeeded through the survivor while the other was hung.
  Left alone, the liveness probe (`airflow jobs check --local`, 5 x 60 s) restarts the hung container about 5 minutes in.
- Outage (1c): `AirflowSchedulerDown` (no `airflow_scheduler_heartbeat` increase for 1 minute) fired after 111–129 s; `GET /api/v2/monitor/health` reported the scheduler `unhealthy`, and nothing new was scheduled.
  After scaling back, the alert resolved within about 25 seconds and the canary succeeded.
- No lock errors in either scheduler's log or in Postgres through PgBouncer's transaction pooling (D6).

Detection: `AirflowSchedulerDegraded` (fewer live `SchedulerJob` rows than desired replicas, from `airflow_jobs_alive`) and `AirflowSchedulerDown`; the "Schedulers" tile shows live against desired, and "Component heartbeats /min" halves on a hang and drops to 0 on an outage.

Diagnosis: which scheduler stopped heartbeating:

```bash
docker compose -f platform/compose/compose.yaml exec -T metadata-db psql -U airflow -d airflow -c \
  "SELECT id, hostname, state, now() - latest_heartbeat AS heartbeat_age FROM job
   WHERE job_type = 'SchedulerJob' AND state = 'running' ORDER BY id"
```

The `hostname` is the pod name.

Recovery: for a hang, `KA delete pod <hostname>` (or wait for the liveness probe); for an outage, `KA scale deploy/airflow-scheduler --replicas=2`, then `KA rollout status deploy/airflow-scheduler`.
A surviving or new scheduler adopts or resets the task instances the lost one had queued.

### 2. Drain a node

Trigger: `kubectl --context kind-pplk8s drain <node running the Celery worker> --ignore-daemonsets --delete-emptydir-data`.

Observed:

- The drain evicted the scheduler, triggerer, statsd-exporter, and worker from `pplk8s-worker`; every pod was Running again on `pplk8s-worker2` within a minute, with none left Pending.
- The canary succeeded on the rescheduled worker while the node was still cordoned.
  Workers keep no volume since remote logging (D22), so nothing pins them to a node.
- `KubeNodeUnschedulable` fired within about 30 seconds and resolved about 25 seconds after the uncordon.
- PgBouncer runs two replicas spread across the nodes behind a PodDisruptionBudget (`maxUnavailable: 1`), so a drain takes down at most one at a time and the Service always keeps an endpoint.
  No Airflow container restarts; the drill fails if one does.
  With a single replica, the drain cut every component's DB connections: in one pass the triggerer restarted within the minute (exit `Error`), and six evictions of a lone replica in a row restarted the scheduler, dag-processor, and triggerer once each.
  A component that loses its connection exits on `sqlalchemy.exc.PendingRollbackError` after `server closed the connection unexpectedly` instead of reconnecting, and the kubelet restarts it.
- When a drain has put both replicas on one node, draining that node evicts them one at a time: kubectl retries the second (`Cannot evict pod as it would violate the pod's disruption budget`) until the first is Ready elsewhere.
- Prometheus keeps its history: it runs on the control plane with its TSDB on a PVC (D21), so a worker drain never moves it.
  Before issue #9 it used an emptyDir, and a drain that moved it erased every series older than the drain.
  The check restarts Prometheus after the drain and requires a `count(up)` sample from before it to read the same.
- The schedulers and triggerers run two replicas each behind PodDisruptionBudgets (`maxUnavailable: 1`, D31), so a drain evicts at most one of each at a time.
  On 2026-10-12 the drain of `pplk8s-worker2` evicted one scheduler and one triggerer; sampled every 2 s through the drain, at least one of each stayed live (a `running` job with a heartbeat under 30 s), and no container restarted.
  A new scheduler pod is Ready only once its startup probe sees its job heartbeat, so the scheduler PDB waits for real capacity; the triggerer has no startup probe in chart 1.22, so its PDB can count a pod that does not heartbeat yet.
- Pods do not move back after the uncordon, so after a drain both replicas of a component can share one node until they are replaced; a later drain of that node then evicts them one at a time through the PDB.
- The dag-processor and api-server still run one replica each without a PDB; a PDB with `minAvailable: 1` would block the drain instead.
  Their eviction pauses parsing and the UI for the restart, and stops no running work.

Detection: `KubeNodeUnschedulable` (severity `info`); if pods cannot fit elsewhere, `AirflowPodsPending` after 2 minutes, and if a replacement scheduler or triggerer never heartbeats, `AirflowSchedulerDegraded` or `AirflowTriggererDegraded`.

Recovery: `kubectl --context kind-pplk8s uncordon <node>`.
Pods do not move back on their own; the scheduler spreads new pods again as they are replaced.

### 3. Stop the metadata DB

Trigger: `docker compose -f platform/compose/compose.yaml stop metadata-db`.
This is the stand-in for a Cloud SQL maintenance or failover window.

Observed:

- `MetadataDBDown` (`pg_up` from the Compose `postgres_exporter`) fired 50–60 seconds after the stop.
- PgBouncer kept accepting client connections, so no pod failed a probe at first; the scheduler stopped heartbeating and `AirflowSchedulerDown` fired about 75 seconds later.
- After the start, the DB alert resolved within 10–30 seconds and the scheduler heartbeated again 15–30 seconds later.
- KEDA's worker query reads the same DB, so its scaler failed too and `KedaScalerErrors` fired about 2.5 minutes into the outage (2026-10-11); the worker count stays frozen until the DB is back (drill 7).
- Three components restarted during the outage, one to three times each per pass: the kubelet killed the scheduler (exit 143) when its DB-backed liveness probe failed, and the dag-processor and triggerer (exit 1) exited on their own when they lost the DB (`psycopg2.OperationalError: server closed the connection unexpectedly`, then `PendingRollbackError`); the api-server and workers did not restart.
  The first pass reported no restarts because its restart counter was broken; trust `kubectl get pods` restart counts.

Detection: `MetadataDBDown`, then `AirflowSchedulerDown`; panels "Metadata DB" and "PgBouncer clients".

Diagnosis: `docker compose -f platform/compose/compose.yaml ps metadata-db`; `KA logs deploy/airflow-scheduler -c scheduler | grep OperationalError`.

Recovery: `docker compose -f platform/compose/compose.yaml up -d --wait metadata-db`.
Components reconnect on their own; check that tasks running during the outage were retried (they fail their heartbeat calls and time out after `task_instance_heartbeat_timeout`).

### 4a. Starve the workers of slots

Trigger: shrink pool `ops_load` to 1 slot (`KA exec deploy/airflow-scheduler -c scheduler -- airflow pools set ops_load 1 "..."`), then trigger `ops_load_test` with `{"tasks": 4, "seconds": 60}`.

Observed:

- `airflow_pool_starving_tasks{pool_name="ops_load"}` rose to 2 and `AirflowPoolStarving` fired after about 90 seconds.
- KEDA did not scale the workers: its query counts running and queued task instances, and starved tasks wait in `scheduled`, before the executor sees them.
  More workers do not help a pool limit; only more slots do.
- After the pool went back to 16, the alert resolved within about 30 seconds and the run succeeded.

Detection: `AirflowPoolStarving`; panels "Pool queued / starving / deferred" and "Pool open slots".
When the executor itself has no free slot, `AirflowTasksQueuedTooLong` fires instead, and KEDA scales the workers (see `tests/e2e/keda-check.sh`).

Recovery: raise the pool (`airflow pools set <pool> <slots> ...`) or wait for the backlog to drain.

### 4b. Starve a worker of memory (OOMKill)

Trigger: trigger `ops_load_test` with `{"tasks": 1, "seconds": 60, "hold_mb": 1700}`; the worker container is limited to 1536Mi.

Observed:

- The kernel OOMKilled the worker container (not just the task process), and `AirflowContainerOOMKilled` fired within about 30 seconds.
- The task failed on try 1, and its run failed; `ops_load_test` uses `retries=0`, so the failure is visible at once.
- The kubelet restarted the container, the canary succeeded on the same pod, and the alert resolved once the restart fell out of its 5-minute window.
- Every task running on that worker died with it; with retries, they come back once their heartbeat is older than `[scheduler] task_instance_heartbeat_timeout`, 120 s since Phase 6 (300 s in Phase 4 drill 1).

Detection: `AirflowContainerOOMKilled`; panels "Airflow memory vs limit (largest pod per container)" and "Container restarts (10m)".

Diagnosis: `KA get pods` (restart count), `KA describe pod <worker>` (`Last State: Terminated, Reason: OOMKilled`).

Recovery: none for the worker; fix the task (smaller batches) or move it to a KubernetesPodOperator pod with its own limit (`docs/executors.md`).
Raising the worker limit only moves the ceiling, because every task on a Celery worker shares it.

### 5. Roll the chart and the Airflow minor version

Trigger: `make phase6-upgrade-drill`.
It works on a throwaway database, `airflow_drill` on the same metadata-db server (`--set data.metadataConnection.db=airflow_drill`), never on the lab's only copy; its exit trap redeploys the normal release and drops `airflow_drill`.
Before every deploy that moves PgBouncer to the other database, the drill stops every Deployment and deletes the PgBouncer pods (issue #11).
Otherwise PgBouncer rolls while the migration Job runs, and the Job reaches whichever database a surviving old PgBouncer pod still serves: the 3.2.2 Job failed on the lab's 3.3.1 schema with `Can't locate revision identified by 'd2f4e1b3c5a7'` and once crash-looped past helm's 10-minute timeout, and the restore's 3.3.1 Job migrated `airflow_drill` instead of `airflow` and reported success.
The steps: install chart 1.21.0 with Airflow 3.2.2 (image `AIRFLOW_DRILL_IMAGE`, with Composer 3.2.2's provider pins), back up the database with `pg_dump -Fc`, preview with `helm diff upgrade`, upgrade to chart 1.22.0 with Airflow 3.3.1, then go back first the wrong way and then the right way.

Observed, upgrade:

- `helm diff` showed 158 changed lines; the upgrade took about a minute, and the migration Job moved the schema from `1d6611b6ab7c` to `d2f4e1b3c5a7`.
- The canary succeeded on both lines.

Observed, the wrong way back (`helm rollback airflow <3.2.2 revision>` alone):

- The rollback restores the 3.2.2 manifests but not the schema, and `airflow db migrate` cannot go back: the migration pod failed with `alembic.util.exc.CommandError: Can't locate revision identified by 'd2f4e1b3c5a7'` and restarted in place (the chart's Job uses `restartPolicy: OnFailure`).
- Every new 3.2.2 pod stayed in `Init:Error`: `wait-for-airflow-migrations` reported `There are still unapplied migrations after 60 seconds. MigrationHead(s) in DB: {'d2f4e1b3c5a7'} | Migration Head(s) in Source Code: {'1d6611b6ab7c'}`.
- The old 3.3.1 pods kept serving, so the API still reported 3.3.1, the canary still worked, and no availability alert fired: the rollback simply never landed.
- `AirflowMigrationJobFailed` fired 90–105 seconds after the rollback, and `AirflowRolloutStuck` 105–110 seconds after that.

Detection: `AirflowMigrationJobFailed` (a still-running migration pod that restarted, or a failed Job), then `AirflowRolloutStuck` (`kube_deployment_status_replicas > kube_deployment_spec_replicas` for 3 minutes); panel "Container restarts (10m)"; `GET /api/v2/version` still shows the newer version.

Diagnosis: `KA logs job/airflow-run-airflow-migrations`; `KA logs <new pod> -c wait-for-airflow-migrations`; `helm --kube-context kind-pplk8s -n airflow history airflow`.

Recovery, the right way back (took about a minute):

1. Stop everything that holds connections: `KA scale deploy --all --replicas=0`.
2. Recreate the database and restore the dump taken before the upgrade: `DROP DATABASE … WITH (FORCE)`, `CREATE DATABASE …`, `pg_restore --no-owner`; check that `alembic_version` is the old head.
3. Redeploy the older line (chart 1.21.0, the 3.2.2 image), which brings every Deployment back to its replica count.

Both alerts resolved, and the canary succeeded on 3.2.2.
Runs recorded between the backup and the restore are lost; on a real platform, take the backup at the start of the change window and pause DAGs until the upgrade is accepted.
On Cloud Composer the upgrade is in place and Google runs the migration; the transferable lesson is that the metadata schema only moves forward, so the way back is a snapshot, not a rollback.

### 6. Scale in a worker while it runs a task

Trigger (automated in `tests/e2e/keda-check.sh`): raise the ScaledObject's minimum by one (`KA patch scaledobject airflow-worker --type merge -p '{"spec":{"minReplicaCount":2}}'`), run `ops_load_test` with `{"tasks": 1, "seconds": N}`, mark the task's worker with `KA annotate pod <worker> controller.kubernetes.io/pod-deletion-cost=-100`, then set the minimum back to 1.
The HPA scales in on its next 15 s loop, and the ReplicaSet deletes the pod with the lowest deletion cost.
A natural burst never shows this: the 120 s stabilisation window keeps every worker until the burst ends.

Observed (`terminationGracePeriodSeconds: 60`):

- The HPA removed the marked pod 10–15 seconds after the minimum dropped; the worker logged `worker: Warm shutdown (MainProcess)` and took no new task.
- A 45 s task, signalled about 14 seconds in, finished during the warm shutdown (`success` on try 1), and the pod exited right after it.
- A 240 s task was SIGKILLed when the 60 s grace expired; it stayed `running` until its heartbeat was 120 s old, and the scheduler failed it about 2 minutes after the pod went.
  `ops_load_test` uses `retries=0`, so the run fails; every business task has `retries ≥ 1` (PLAN.md D24), so there the failure becomes a retry, as in Phase 4 drill 1.

Detection: a lost task shows as `AirflowTaskFailures` (or a retry) and on the panels "Task outcomes /min" and "Celery workers"; the scale-in itself is normal and raises no alert.
If workers do not scale in (or out) at all, check the scaler before anything else: `KA describe hpa keda-hpa-airflow-worker` (`FailedGetExternalMetric`) and `kubectl -n keda logs deploy/keda-operator`.
Through PgBouncer it failed on most polls with `prepared statement "stmtcache_…" already exists` until PgBouncer got `max_prepared_statements` (PLAN.md D6); `KedaScalerErrors` now catches that (drill 7).

Recovery: none for the scale-in; a killed task retries on its own.
Keep tasks that outlast the grace period off the workers' critical path: defer long waits to the triggerer, and give every worker task retries.

### 7. Break the KEDA scaler

Trigger: point the worker ScaledObject's trigger at a table that does not exist, `KA patch scaledobject airflow-worker --type json -p '[{"op":"replace","path":"/spec/triggers/0/metadata/query","value":"SELECT count(*) FROM pplk8s_no_such_table"}]'`.
It stands in for any scaler fault: wrong DB credentials, PgBouncer down, or the prepared-statement clash that froze the workers for about 4 minutes on 2026-10-11 (issue #7).

Observed:

- KEDA's PostgreSQL scaler failed on every poll (about 15 failed polls a minute); the ScaledObject went `Ready=False` (`TriggerError`) and the HPA's `ScalingActive` reason became `FailedGetExternalMetric`.
- `keda_scaler_metrics_value` vanished, the worker count stayed where it was (1), and nothing else failed: no pod restarted, and the canary still ran.
- `KedaScalerErrors` fired 147 seconds after the change (2026-10-11); after the query was restored, the ScaledObject was `Ready` again and the alert resolved 57 seconds later.
- Back-tested over the prepared-statement clash of 2026-10-11 08:35–09:00 UTC, the same expression held true throughout, so the alert would have fired around 08:37.
- With the KEDA operator scaled to 0 (by hand, not in the check), `KedaMetricsMissing` fired about 2.5 minutes later and resolved within a scrape of the operator coming back.

Detection: `KedaScalerErrors` (`keda_scaled_object_errors_total` rising for 2 minutes); panels "KEDA scaler failed polls /min" and "KEDA worker target vs workers" (the target line has gaps while the worker count stays flat).
Alert on `keda_scaled_object_errors_total`, not `keda_scaler_detail_errors_total`: during the prepared-statement clash the first counted 198 failed polls and the second stayed at 0.
The HPA's `ScalingActive` condition is a weak signal, because it flips back to `True` on every poll that succeeds.
`KedaMetricsMissing` fires when Prometheus does not scrape the KEDA operator at all; its ServiceMonitor lives in `platform/monitoring/manifests/airflow-monitors.yaml`, not in the KEDA chart, so the scrape exists whichever stack is deployed first.

Diagnosis: `KA get scaledobject airflow-worker` (`READY False`, reason `TriggerError`); `KA describe hpa keda-hpa-airflow-worker` (`FailedGetExternalMetric` events); `kubectl --context kind-pplk8s -n keda logs deploy/keda-operator | grep -i error` names the failing query or connection.

Recovery: fix the cause the operator log names (here, restore the chart's query: `make airflow-up`, or patch the old query back).
The HPA resumes on its next poll; workers that were held through the outage scale in after the 120 s stabilisation window.

### 8. Restart the Celery broker

Trigger: `KA delete pod airflow-redis-0`.
Redis is the Celery broker and keeps no data (`redis.persistence.enabled: false`), so a restart, an eviction, or an OOMKill drops every message it holds; workers reconnect within 2–3 seconds.
Nothing in Airflow notices the restart itself; what goes wrong depends on what the broker held.

Observed (2026-10-11):

- With every task already running (12 across 3 workers), the tasks finished on try 1 and the run succeeded.
- **A task waiting in the broker is lost.** Its message vanished with Redis, but the task instance stayed `queued` and no worker ever saw it: `plan` waited 11 minutes, until the scheduler's stuck-in-queued check requeued it (`task_queued_timeout` 600 s plus up to one 120 s check interval; log `Task stuck in queued; will try to requeue`), and nothing fired before this drill added `AirflowTasksStuckQueued`.
  The check runs automated as 8a: KEDA paused at 0 workers (`autoscaling.keda.sh/paused-replicas: "0"`), `hello` triggered (`LLEN default` = 1), Redis restarted (`LLEN default` = 0), KEDA resumed; `AirflowTasksStuckQueued` fired after 187 s with a worker up and `say_hello` still `queued`.
- **A worker that was running a task when the connection dropped used to stall, in two ways** (issue #15, fixed).
  First, it took no new task until the running one ended: in 8b, `hello` waited 256 s behind a 240 s task while the worker had 3 free slots.
  KEDA did not help: its demand, `ceil((running + queued) / 4)`, was already met by the stalled worker.
  Cause: on every reconnect Celery's `Consumer.on_close` calls `AsynPool.flush`, which clears the pool's set of busy processes, so the fair scheduler wrote `hello` into the pipe of the process still running the long task (celery/celery#10346).
  Second, and more often, the worker stopped answering `celery inspect ping` until the liveness probe killed it, and the running task with it.
  Cause: a `SIGUSR1` stack dump showed the main thread blocked in kombu's `_brpop_read` on a dead Redis socket that has no timeout, so the event loop never ran again (same trace as celery/celery#8091).
  The settings issue #15 proposed do not help: `worker_enable_prefetch_count_reduction = False` and `worker_disable_prefetch = True` still stall, and `worker_cancel_long_running_tasks_on_connection_loss = True` frees the slot by cancelling the running task.
  The fix (`values.yaml`): `[celery_broker_transport_options] socket_timeout = 10`, so a dead read raises and Celery reconnects, and `[celery] celery_config_options = pplk8s.celery_config.CELERY_CONFIG`, Airflow's default config plus a backport of Celery 5.7's busy-process fix to the installed 5.6.3.
  Since then, in three runs of 8b, `hello` started 2–5 s after it was queued, the worker kept answering pings and was not restarted, and the 240 s task succeeded on try 1.
  The worker liveness probe stays 30 s x 3 (`workers.celery.livenessProbe`) for any other wedge.
- An idle worker is not affected: pings and new tasks worked right after the restart.

Detection: `AirflowTasksStuckQueued` (task instances in `queued` for 3 minutes; panel "Pool queued / starving / deferred"); `AirflowComponentUnavailable` if Redis stays down for 2 minutes (it covers StatefulSets now).
The worker's log shows `consumer: Connection to broker lost` and then `Connected to redis://...`.
The same alert fires when demand outruns KEDA's maximum, so check the broker before adding workers.

Diagnosis: `KA get pods airflow-redis-0` (age, restarts); `KA logs deploy/airflow-worker -c worker | grep -E "broker lost|Connected to redis|prefetch"`; a queued task instance whose message is gone has an empty queue behind it: `KA exec airflow-redis-0 -- sh -c 'redis-cli -a "$REDIS_PASSWORD" --no-auth-warning llen default'` reads 0.

Recovery:

1. Clear the stuck task instances (UI, or `POST /api/v2/dags/<dag>/clearTaskInstances` with `task_ids`); in 8a `say_hello` succeeded 5 seconds later on try 2 and the alert resolved 27 seconds after that.
   Left alone, the scheduler requeues them after `task_queued_timeout`, at most twice, and marks the third stuck attempt failed.
2. If tasks still stay queued behind a worker that ran through the restart (a regression of issue #15), dump its stacks with `KA exec <worker> -c worker -- python -c 'import os, signal; os.kill(<MainProcess pid>, signal.SIGUSR1)'` (the pid whose `/proc/<pid>/cmdline` names `MainProcess`; the stacks go to the worker log), then restart it (`KA delete pod <worker>`); its running tasks die and retry (every business task has `retries ≥ 1`, PLAN.md D24).

`task_queued_timeout` stays 600 s: lowering it would also requeue, and on the third time fail, tasks that only wait for capacity during a burst.

### 9. Lose a triggerer while a readiness wait is deferred

Trigger: with a `finance_daily` run's `wait_*` tasks `deferred` on two triggerers (D31), hang the triggerer that holds a wait (9a: SIGSTOP its `airflow triggerer` job process), crash it (9b: SIGKILL; the image has no `kill`, so `KA exec <pod> -c triggerer -- python -c 'import os, signal; os.kill(<pid>, signal.SIGKILL)'`), or stop them all for longer than the alert window (9c: `KA scale deploy/airflow-triggerer --replicas=0`).
While a wait's triggerer is gone, mark its upstream `ready` in `ops.readiness`.
The check uses the interval [2026-09-30, 2026-10-01), which no producer builds, and writes its ledger rows with `run_id = 'phase6-check'`.

How a trigger moves: each trigger row belongs to one triggerer job (`trigger.triggerer_id`).
Another triggerer claims it only when that job has an `end_date` (a clean stop on SIGTERM) or its last heartbeat is older than `[triggerer] triggerer_health_check_threshold` (30 s; `Trigger.assign_unassigned`).
Every triggerer runs that assignment on each loop, so the survivor and a crashed pod's restarted container race for orphaned triggers.
Nothing else watches deferred tasks: without a triggerer they stay `deferred`, hold no worker slot, and fail no one.

Observed with two triggerers (2026-10-12):

- Hang (9a): the survivor claimed the hung job's trigger 23 s after the SIGSTOP, when the hung job's last heartbeat was 31 s old (the hang started part-way through a heartbeat interval), and `wait_sales_gold` succeeded 3 s after its upstream turned ready, on try 1.
  `AirflowTriggererDegraded` fired 170 s after the hang; `AirflowTriggererDown` stayed quiet, because the survivor kept heartbeating.
  Deleting the hung pod takes the full 60 s grace period, because a stopped process cannot act on SIGTERM.
- Crash (9b): the trigger was claimed once, 24 s after the kill, at a dead-job heartbeat age of 32 s; in that run the crashed pod's restarted container won the race against the other triggerer.
  The dead job's row stays `running` with no `end_date`; that is harmless, because assignment checks the heartbeat, and the daily `airflow-database-cleanup` CronJob (`airflow db clean`, D30) deletes it once its heartbeat is 60 days old.
  With one triggerer, the restarted container was up within about 8 s and then waited, holding none of the triggers, until the dead job was 30–31 s stale.
- Pod deletion, even `--grace-period=0 --force`, is not a crash: the kubelet still sends SIGTERM, the job ends cleanly, and another triggerer claims the triggers on its next loop (19 s from the delete to the wait resuming with one triggerer).
- Outage (9c): `AirflowTriggererDown` fired after 175–195 s.
  `wait_returns_silver` stayed `deferred` the whole time with its upstream already `ready`, holding no worker slot (`default_pool` running 0), and its trigger stayed with the stopped job.
  `/api/v2/monitor/health` reported the triggerer `unhealthy`, with the heartbeat of the most recent job still marked `running` (an earlier crashed one), not of the job that stopped.
- After the scale-up the triggerers were Ready in 6–22 s and the wait succeeded 15–25 s after the scale-up; the alert resolved 15–35 s after that, and the run built `finance` exposed and recorded `finance.exposed`, with every task on try 1.
- The outage counts against the sensor's timeout: `task_instance.trigger_timeout` is fixed when the task defers (defer time + 6 h for `finance_daily`), so an outage longer than the remaining time fails the wait at the next scheduler check.
- The AssetWatcher spike's `PubsubPullTrigger` (D17) runs in the same triggerer and pauses with it; the event adapter does not.

Detection: `AirflowTriggererDegraded` (fewer live `TriggererJob` rows than desired replicas) and `AirflowTriggererDown`; the "Triggerers" tile shows live against desired, "Component heartbeats /min" halves on a hang and drops to 0 on an outage, and "Pool queued / starving / deferred" keeps deferred flat.
A crash that the kubelet restarts within the 2-minute window fires nothing; the waits only resume late by up to `triggerer_health_check_threshold`.

Diagnosis: who holds the deferred triggers and how fresh is their job:

```bash
docker compose -f platform/compose/compose.yaml exec -T metadata-db psql -U airflow -d airflow -c \
  "SELECT t.id, t.triggerer_id, j.hostname, j.state, j.end_date, now() - j.latest_heartbeat AS heartbeat_age
   FROM trigger t LEFT JOIN job j ON j.id = t.triggerer_id"
```

Recovery: for a hang, `KA delete pod <hostname of the stale job>` (the liveness probe restarts it about 5 minutes in otherwise); for an outage, `KA scale deploy/airflow-triggerer --replicas=2`, then `KA rollout status deploy/airflow-triggerer`.
A live triggerer claims every orphaned trigger, and a trigger whose condition came true during the outage fires on its first poll; nothing needs clearing.
If the outage outlasted a wait's timeout, the task failed: clear it once its upstream is ready.

### 10. Restore the metadata DB to an earlier point

A metadata DB restore (Cloud SQL backup or point-in-time recovery, a Composer snapshot load) rolls Airflow's history back while the warehouse keeps every row written since.
Restored Airflow is healthy by every other signal; the drift is visible only where the two histories meet, the readiness ledger (D32).

Trigger: `make metadata-restore-drill`.
It backs up the metadata DB with `pg_dump -Fc` while Airflow runs, then runs three pipelines past the backup for interval 2026-10-06: `sales_elt`, a returns file through the event path (`returns_file_arrival`), and `finance_daily` waiting on both.
Then it restores the backup in place, the way drill 5's right way back does: every Airflow Deployment scaled to 0 (KEDA paused at 0 for the workers), the PgBouncer pods deleted, `DROP DATABASE airflow WITH (FORCE)`, `CREATE DATABASE`, `pg_restore --no-owner`, and the Deployments scaled back.
The interval must not precede the DAGs' `start_date` (2026-10-01): Airflow creates no task instances for a run whose logical date is earlier, and the empty run succeeds at once.

Observed (2026-10-12):

- The restore took 2 min 14 s from stopping Airflow to the canary; the backup was 708K.
- The three runs were gone from Airflow, and the warehouse was untouched: gold, exposed, `silver.returns`, the interval's `ds_source` rows, `ops.file_loads`, and `ops.readiness` hashed the same before and after.
- The scheduler re-created nothing for the three manual and event runs.
  In one of three passes, a scheduled run had been queued just after the backup (`finance_daily`'s latest, from the drill unpausing it), and the scheduler re-created it under the same `scheduled__` id.
  With `catchup=False` the scheduler only ever creates the latest interval's run, so a restore never backfills the gap; with `catchup=True` it would re-run every interval since the backup.
- `AirflowMetadataBehindWarehouse` fired once per lost run, 80 seconds after Airflow came back in every pass (the rule's `for: 2m` started while Airflow was still starting).
- A redelivered file event re-created its run under the same deterministic id (D18), and the run short-circuited on `ops.file_loads` (`load` skipped): no second load, and that run's alert resolved 20–25 seconds later.

Detection: `AirflowMetadataBehindWarehouse`, one alert per run, labelled with its `dag_id` and `run_id`; the Grafana "Firing alerts" table lists them.

Diagnosis: `scripts/metadata-reconcile.sh` lists every run that wrote `ops.readiness` rows in the last 7 days but is unknown to Airflow, with its interval and products.
`SELECT max(dttm) FROM log` on the restored database shows how far back it went.

Recovery:

1. Unpause the business DAGs the lost runs belong to (a run on a paused DAG never starts; the restore also brought back each DAG's paused flag as of the backup).
2. `scripts/metadata-reconcile.sh --replay` re-creates the lost runs one at a time, in the order they finished, and waits for each.
   Manual and event runs keep their own ids, so the ledger matches Airflow again; a lost scheduled run is replayed as a manual run for the same interval, because its `scheduled__` id belongs to the scheduler.
   An event run gets its event back from `ops.file_loads` and short-circuits on it.
3. The replays rewrite the same rows (D15): `sales_elt` then `finance_daily` took 76 seconds together, the warehouse and `ops.readiness` hashed the same after them, the alert resolved 10–15 seconds later, and the canary succeeded.

The order matters: replayed together, a consumer starts at once (its producers' readiness rows are already `ready`, left by the lost runs) and builds before its producers are rebuilt.
In the first attempt `finance_daily`'s replay built `exposed.net_sales_daily` 12 seconds before `sales_elt`'s replay rebuilt `gold.daily_sales`, whose `DROP ... CASCADE` then deleted the finance view (issue #27).

Prevention: before a planned restore, note the backup's timestamp and expect to replay everything that finished after it; on Composer, a snapshot load is the same operation and needs the same reconcile.

### 11. git-sync cannot fetch (DAGs go stale)

Every pod that loads DAG files (dag-processor, triggerers, workers) runs a git-sync sidecar that fetches `main` every 10 s (D23); the schedulers have none, because Airflow 3 schedulers read serialized DAGs from the metadata DB.
A fetch can start failing at any time: the ref is deleted or renamed, the deploy key is revoked or rotated, or GitHub is unreachable.
git-sync then keeps serving its last good commit, so Airflow keeps running, but no DAG change arrives.

Trigger: `DRILLS=11 make phase6-check`, or by hand, a NetworkPolicy that leaves every egress port open except TCP 22 for those pods (`tests/e2e/phase6-check.sh`, `block_git_ssh`).
It stands in for every fetch failure after a good sync; a deleted ref and a revoked key fail the same `git fetch` and take the same path through git-sync.

Observed (2026-10-12):

- Before the fix (#18), the chart's `maxFailures: 0` made git-sync exit on its first failed fetch ("too many failures, aborting", 31 s after the block): the sidecar crash-looped and took its pod out of Ready, while the Airflow container kept serving the old commit.
  The failure was loud, but as `AirflowComponentUnavailable`, which points at the wrong cause; a GitHub blip of one period would have done the same.
- With `maxFailures: -1`, git-sync logs `error syncing repo, will retry` and keeps serving the old commit; all 4 pods stayed Ready and nothing restarted.
- `AirflowGitSyncFailing` fired for all 4 pods 176–186 seconds after the block (2-minute window plus `for: 1m`), and resolved 30–61 seconds after the block was removed, without any restart.
- A sidecar that cannot sync at all on a new pod still fails loudly: the one-shot init container exits on its failure, so the new pods stay `Init:CrashLoopBackOff` and the old ones keep serving (seen once while building this, with a bad init flag; a bad ref in a deploy takes the same path, and `AirflowRolloutStuck` covers it).

Detection: `AirflowGitSyncFailing`, one alert per pod, from git-sync's own counters (`git_sync_count_total{status="success|noop|error"}`, scraped by PodMonitor `airflow-git-sync` on port 1234).
Readiness, restarts, and `AirflowComponentUnavailable` stay quiet by design.

Diagnosis: `KA logs <pod> -c git-sync --tail=20` names the failing command and its stderr: `couldn't find remote ref` (ref deleted), `Permission denied (publickey)` (key revoked), or `context deadline exceeded` / `Connection timed out` (unreachable).
`KA exec deploy/airflow-dag-processor -c dag-processor -- readlink /opt/airflow/dags/repo` shows the commit still served; compare with `git ls-remote origin main`.

Recovery: fix the cause the log names: restore or re-point the ref (`dags.gitSync.ref`, then `make airflow-up`), re-add the deploy key (`gh repo deploy-key add ~/.ssh/pplk8s-deploy.pub`), or restore network access.
git-sync resumes on its next period with no restart; the alert resolves within about a minute.

### 12. A data product is late

Every other drill breaks the platform; this one breaks the data contract it serves.
A product is late when its newest `ready` interval in `ops.readiness` ended longer ago than its deadline in `ops.product_deadlines` (D37): `sales` and `finance.exposed` are due 36 hours after their interval starts, which is 12 hours after it ends (noon UTC).
Nothing has to fail for that: a paused DAG, a scheduler that never creates the run, a run stuck deferred, or a producer outside Airflow that stopped all look the same.

Trigger: `DRILLS=12 make phase6-check`.
It pauses `sales_elt` and tightens sales' deadline to one minute (`UPDATE ops.product_deadlines SET max_age = interval '1 minute' WHERE product = 'sales'`), so the newest ready interval counts as late without waiting 36 hours.
It needs one ready `sales` interval and sales not already late.

Observed (2026-10-14, without the cluster: Prometheus v3.15.0 in a container on the Compose network, scraping `warehouse-sql-exporter` and evaluating `airflow-rules.yaml` every 15 s; the drill itself has not run yet):

- With `sales` and `finance.exposed` ready up to 2026-10-14 00:00 (4 h 18 m old), nothing fired.
- Tightening sales' deadline to one minute fired `DataProductLate` for `sales` only, 2 min 18 s later ("sales is late: its newest ready interval ended 4h 21m 11s ago."); `finance.exposed` stayed quiet.
- Re-applying `01-schemas.sql` resolved it within 10 seconds.
- With no ready rows at all, both products fired ("it was never ready").

Observed on the lab (2026-10-14, kind + kube-prometheus-stack, `DRILLS=12 tests/e2e/phase6-check.sh`):

- `sales` ready up to 2026-10-14 00:00; tightening its deadline fired `DataProductLate` for `sales` after 139 s (the 1-minute deadline, the 30 s scrape and the rule's `for: 2m`); `finance.exposed` was already firing, as expected while `finance_daily` stays paused.
- Restoring the deadline and unpausing `sales_elt` resolved it after 16 s; the canary passed.

Detection: `DataProductLate`, one alert per product, labelled `product`; its value is the age of the newest ready interval.
It comes from the warehouse's `sql_exporter` (`ops_product_ready_interval_end_seconds`, `ops_product_max_age_seconds`); if that exporter is gone, `AirflowReadinessMetricsMissing` fires instead.
It is left out of the drills' "nothing firing" preflight: `finance_daily` stays paused on the lab (#66), so `finance.exposed` is late by design until a synthetic partner drop exists.

Diagnosis: find the product's producer and why it did not land.
`psql -h localhost -p 5433 -U warehouse warehouse -c "SELECT product, interval_start, interval_end, status, dag_id, run_id, updated_at FROM ops.readiness WHERE product = '<product>' ORDER BY interval_end DESC LIMIT 3"` shows the newest rows and the run that wrote them.
Then, in Airflow: is the DAG paused, has the scheduler created the interval's run, is the run deferred on an upstream product (the sensor names it), or did a task fail.

Recovery: fix the cause (unpause, clear the failed task, land the upstream product); the alert resolves within about a minute of the interval's `ready` row, after the next scrape.
A product that is late on purpose (retired, or a source that skipped a day) gets its deadline changed in `platform/compose/warehouse-init/01-schemas.sql`, not silenced; `make services-up` re-applies it.

## Phase 8 drills

Phase 8 drills exercise the TLC monthly pipeline (PLAN.md D34–D36) under the same contract as Phase 6: each drill is detected by an alert and recovered through its entry here (D28).
Workload alerts live in `platform/monitoring/manifests/workloads-rules.yaml`; their promtool tests run with `make rules-test`.

### 1. A big month against EL Factory's memory ceiling

EL Factory gets 1 GiB per pod (D35) and stages one TLC chunk (one Parquet row group) at a time per gunicorn process, so a pod holds at most two chunks.
FHVHV has the heaviest chunks: about 1 M rows and 25 columns in a 23–27 MiB row group.

Measure: `make el-factory-memory-drill`.
It loads two real chunks of each of three FHVHV months (2026-05, 2026-08, 2025-02) concurrently through one pod, then reports the pod's cgroup `memory.peak` and every process's `VmHWM`.
It fails if the pod restarted or the peak reached 85 % of the limit, and on exit drops `ds_source.tlc_fhvhv` and its chunk ledgers (FHVHV stays disabled in the catalog).

Observed (2026-10-14, el-factory 0.7.0):

- Peak 530–670 MiB per pod over three runs (51–65 % of the limit), with each process at 345–455 MiB RSS against about 130 MiB idle.
- Before 0.7.0 the same load peaked at 967 MiB, 57 MiB under the limit: `COPY` read 100,000-row CSV parts, each copied about four times (Arrow table, CSV buffer, `getvalue()`, libpq), about 250 MiB per process; 25,000-row parts run as fast.
- Yellow 2023-01, the largest chunk in scope (one 45 MiB row group of 3.1 M rows), peaks at 316 MiB in one process.
- FHVHV 2023-01 is a single 451 MiB row group; staging it alone peaked at 1.5 GiB, so EL Factory refuses any chunk over 64 MiB compressed with a non-retryable 422 before it stages anything or touches the landing table (answered in 0.2 s, pod at 165 MiB).

Detect: `make el-factory-memory-drill TIGHT_LIMIT=448Mi`.
It shrinks EL Factory's limit to 448Mi, repeats the load until both alerts fire, then patches the saved resources back.

Observed (2026-10-14):

- The first load OOMKilled the container within 40 s (`Empty reply from server` on every in-flight request); `WorkloadContainerOOMKilled` fired 27 s later.
- `WorkloadContainerMemoryNearLimit` fired only after the second OOMKill, 3 min 40 s in: a chunk climbs from idle to the limit inside one 10 s cAdvisor scrape, so the kill comes before any scrape sees 85 %.
  The near-limit alert catches a peak that creeps up without crossing the limit (a bigger month, a wider schema), not a single chunk that overshoots; for that, the 64 MiB chunk cap is the guard.
- Two restarts, last termination `OOMKilled`; the drill then restored 1Gi/512Mi and both pods came back Ready.

Detection: `WorkloadContainerMemoryNearLimit` (the 5-minute maximum working set over 85 % of the container's limit; its value is the ratio) and `WorkloadContainerOOMKilled` (an OOMKill with a restart in the last 5 minutes).
Both cover every container in `workloads`.

Diagnosis: `$K get pods` (restarts), `$K describe pod <pod>` (`Last State: Terminated, Reason: OOMKilled`), and the Airflow task's log: an OOMKilled EL Factory answers the hook with a dropped connection, which the hook treats as retryable.
Which month and chunk: EL Factory's access log on the restarted container (`$K logs <pod> --previous`) shows the last `/extract` requests.
A 422 `chunk N is ... bytes compressed, over the 67108864-byte limit` is the chunk cap, not an OOMKill: that file cannot be loaded by chunks, and retrying cannot help.

Recovery: nothing to undo; the kubelet restarts the container and the task's retry resumes after the last loaded chunk (D34).
If the near-limit alert keeps firing, measure with `make el-factory-memory-drill` before changing anything: lower `CSV_BATCH_ROWS` or `MAX_CHUNK_BYTES` in `services/el-factory/src/el_factory/chunks.py` first, and raise the 1Gi limit only with a matching change to D35.

### 2. Lose EL Factory in the middle of a file

EL Factory loads a TLC file one chunk (one Parquet row group) at a time, and `ops.file_chunks` records each chunk in the same transaction as its rows (D34).
A pod lost in the middle of a chunk rolls that chunk's transaction back, so the task's retry asks again without a cursor and EL Factory resumes at the first chunk the ledger lacks.

Drill: `make tlc-resume-drill`.
It forgets the chunk ledger of the newest loaded yellow month, clears that month's `tlc_monthly` run, and once 2 of the file's 4 chunks are recorded force-deletes the EL Factory pod holding the extract's connection (`--grace-period=0 --force`, so the request in flight dies with the pod as on a lost node; a graceful delete gives it up to the pod's 30 s grace period to finish).
It then asserts that the retry loaded only the missing chunks, that landing rows = ledger rows = the Parquet footer's row count, that the file has one completed version, and that the month's landing, silver and quarantine counts did not change.

Observed (2026-10-14, yellow 2026-08, 4 chunks, 3,336,716 rows):

- The kill came 42 s after the clear, with chunks 0 and 1 recorded; the extract attempt failed at once on the dropped connection (retryable, D15) and went `up_for_retry`.
- `AirflowTaskFailures` fired 37 s after the kill.
- The retry started 5 minutes later, loaded chunks 2 and 3 in about 6 s on the surviving pod, and completed the version; chunks 0 and 1 kept their first `loaded_at`.
- The first run of the drill found `AirflowTaskFailures` blind to a one-off failure (fixed in #91): the statsd-exporter creates a task's `airflow_ti_failures` series at 1 and drops it 5 minutes after its last update, and `increase()` needs two samples, so a single failed attempt never counted.
  The rule now also fires on a series that did not exist 10 minutes earlier.

Detection: `AirflowTaskFailures` (info) and the task's `up_for_retry` state.
EL Factory's own pod loss raises no alert: the Deployment replaces the pod, and the second replica served the retry.

Diagnosis: the extract's task log shows the dropped connection (`ElFactoryTransientError`); `ops.file_chunks` shows how far the file got:

```bash
docker compose -f platform/compose/compose.yaml exec -T warehouse psql -U warehouse -d warehouse -c \
  "SELECT chunk, rows, loaded_at FROM ops.file_chunks WHERE source_uri LIKE '%yellow_tripdata_2026-08%' ORDER BY chunk"
```

Recovery: nothing to do; the retry resumes.
Why it waited 5 minutes: `extract` retries with exponential backoff from 30 s, capped at `max_retry_delay` (5 minutes), and the exponent is the task instance's `try_number`, which keeps counting across clears.
A first failure waits 30–60 s (Airflow adds up to one more delay of jitter); after a clear or two, the first retry already waits the cap.
