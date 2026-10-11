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

Fix: use a tag that exists (`make push` publishes `0.1.0`), then `workloads-up.sh`.

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
Drills 1–4 and 7 are automated in `tests/e2e/phase6-check.sh` (`make phase6-check`): inject, wait for the alert to fire, run the recovery below, wait for it to resolve, then run the `hello` canary on a Celery worker.
Drill 5 reinstalls Airflow and lives in `tests/e2e/phase6-upgrade-drill.sh` (`make phase6-upgrade-drill`).
Drill 6 is part of the KEDA check, `tests/e2e/keda-check.sh`, which `make phase6-check` runs first.
Times below are from the passes on 2026-10-10; Prometheus scrapes and evaluates rules every 15 s, so each detection time includes up to one interval on top of the rule's `for:`.
`KA` stands for `kubectl --context kind-pplk8s -n airflow`.

### 1. Kill the scheduler

Trigger: `KA scale deploy/airflow-scheduler --replicas=0`.
Deleting the pod is not a useful drill: the Deployment replaces it within seconds, faster than any alert window.

Observed:

- `AirflowSchedulerDown` (no `airflow_scheduler_heartbeat` increase for 1 minute) fired about 2 minutes after the scale-down.
- `GET /api/v2/monitor/health` reported the scheduler `unhealthy`; the api-server, workers, and triggerer stayed up, and nothing new was scheduled.
- After scaling back to 1, the alert resolved within about 25 seconds and the canary succeeded.

Detection: `AirflowSchedulerDown`; panel "Component heartbeats /min" (the scheduler line drops to 0) and "Health".

Recovery: `KA scale deploy/airflow-scheduler --replicas=1`, then `KA rollout status deploy/airflow-scheduler`.
A new scheduler adopts or resets the tasks the old one left queued.

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
- PgBouncer is the only chart component with a PodDisruptionBudget.
  The others run one replica each, so a PDB with `minAvailable: 1` would block the drain instead.

Detection: `KubeNodeUnschedulable` (severity `info`); if pods cannot fit elsewhere, `AirflowPodsPending` after 2 minutes.

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
