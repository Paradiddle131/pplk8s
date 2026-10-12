#!/usr/bin/env bash
# Phase 6 exit check (PLAN.md D28): every failure drill is detected by a firing Prometheus alert and
# recovered by its docs/runbook.md procedure, proven by the alert resolving and a canary DAG run.
#   1a crash one of two schedulers mid-run              -> work keeps moving, no task runs twice (#20)
#   1b hang one of two schedulers (SIGSTOP)              -> AirflowSchedulerDegraded; the survivor schedules
#   1c stop every scheduler (sustained: scaled to 0)     -> AirflowSchedulerDown
#   2  drain the node that runs the Celery worker       -> KubeNodeUnschedulable
#      (then restart Prometheus: its history from before the drain must survive)
#   3  stop the metadata DB                              -> MetadataDBDown
#   4a starve pool ops_load of slots                     -> AirflowPoolStarving
#   4b starve a worker of memory (a task over its limit) -> AirflowContainerOOMKilled
#   7  break KEDA's worker scaler (a query that fails)   -> KedaScalerErrors
#   8a restart the Celery broker holding a queued task   -> AirflowTasksStuckQueued (message lost)
#   8b restart the Celery broker while a task runs       -> new work starts at once, the running task survives (#15)
#   9a hang the triggerer holding a deferred wait        -> the survivor claims the trigger once the hung
#      one's heartbeat is stale, AirflowTriggererDegraded; the wait resumes on try 1 (#17, #20)
#   9b crash the triggerer holding a deferred wait       -> claimed once by another job after the threshold
#   9c stop every triggerer (sustained: scaled to 0)     -> AirflowTriggererDown; the wait stays deferred with
#      its upstream ready, then resumes on scale-up and finance_daily succeeds
#   11 block git-sync's SSH egress to GitHub           -> AirflowGitSyncFailing, every pod still Ready (#18)
# DRILLS="1 9" runs only those drills after the preflight.
# The chart and Airflow minor roll lives in phase6-upgrade-drill.sh (it reinstalls Airflow).
# Expects `make airflow-up observability-up workloads-up`. Re-runnable and self-restoring: the exit trap (also on
# SIGINT/SIGTERM) deletes a pod it hung, scales the schedulers and triggerers back, starts the DB, uncordons nodes, and
# restores the pool, KEDA's query, KEDA's scaling of the workers, git-sync's egress, and the DAGs' paused flags, and
# discards the scheduled runs that unpausing them created.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
source "$(dirname "$0")/lib/airflow-api.sh"
source "$(dirname "$0")/lib/prometheus.sh"
COMPOSE=(docker compose -f "$REPO/platform/compose/compose.yaml")
LOAD=ops_load_test
FIN=finance_daily
OUR_ALERTS='Airflow.*|MetadataDB.*|KubeNode.*|Keda.*'
say() { echo "[$(date +%T)] $*"; }

# ---- restorable state -------------------------------------------------------------------------------
load_was_paused="" fin_was_paused="" keda_query="" hung="" sampler="" git_blocked=""
STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# The replica counts the drills restore (D31: two each); read before any drill changes them.
SCHEDULERS=$(kc get deploy airflow-scheduler -o jsonpath='{.spec.replicas}')
TRIGGERERS=$(kc get deploy airflow-triggerer -o jsonpath='{.spec.replicas}')
cleanup() {
  local rc=$? node
  set +e
  [ -z "$sampler" ] || kill "$sampler" 2>/dev/null
  [ -z "$hung" ] || kc delete pod "$hung" --wait=false >/dev/null 2>&1
  kc scale deploy/airflow-scheduler --replicas="${SCHEDULERS:-2}" >/dev/null 2>&1
  kc scale deploy/airflow-triggerer --replicas="${TRIGGERERS:-2}" >/dev/null 2>&1
  "${COMPOSE[@]}" start metadata-db >/dev/null 2>&1
  for node in $(kubectl --context "$CTX" get nodes -o jsonpath='{range .items[?(@.spec.unschedulable==true)]}{.metadata.name}{" "}{end}'); do
    kubectl --context "$CTX" uncordon "$node" >/dev/null && echo "uncordoned $node"
  done
  pool_size 16 >/dev/null 2>&1
  [ -z "$keda_query" ] || keda_set_query "$keda_query" >/dev/null 2>&1
  keda_resume >/dev/null 2>&1
  [ -z "$git_blocked" ] || kc delete networkpolicy drill-block-git-ssh --ignore-not-found >/dev/null 2>&1
  if [ "$load_was_paused" = true ]; then
    api PATCH "/api/v2/dags/$LOAD" '{"is_paused":true}' >/dev/null 2>&1
    discard_scheduled_runs "$LOAD" "$STARTED"
  fi
  if [ "$fin_was_paused" = true ]; then
    api PATCH "/api/v2/dags/$FIN" '{"is_paused":true}' >/dev/null 2>&1
    discard_scheduled_runs "$FIN" "$STARTED"
  fi
  stop_prometheus
  stop_port_forward
  exit $rc
}
trap cleanup EXIT

# ---- helpers ----------------------------------------------------------------------------------------
psql_meta() { "${COMPOSE[@]}" exec -T metadata-db psql -U airflow -d airflow -Atc "$1"; }
psql_wh() { "${COMPOSE[@]}" exec -T warehouse psql -U warehouse -d warehouse -Atc "$1"; }
pool_size() { kc exec deploy/airflow-scheduler -c scheduler -- airflow pools set ops_load "$1" "KEDA load fixture (ops_load_test)" >/dev/null; }
# Info-level alerts (recent task failures, a cordoned node) describe history, not an outage.
firing_ours() { prom "ALERTS{alertstate=\"firing\", alertname=~\"$OUR_ALERTS\", severity!=\"info\"}" | jq -r 'map(.metric.alertname) | unique | join(",")'; }
wait_ready() { # every Airflow Deployment and StatefulSet rolled out
  local obj
  for obj in $(kc get deploy,statefulset -o name); do
    kc rollout status "$obj" --timeout=300s >/dev/null || fail "$obj not ready"
  done
}
wait_api() { # the api-server answers again (after a DB outage or a drain)
  local end=$((SECONDS + 300))
  until curl -sf -o /dev/null "$API/api/v2/version" 2>/dev/null; do
    [ $SECONDS -lt $end ] || fail "api-server did not come back"
    start_port_forward >/dev/null 2>&1 || true
    sleep 5
  done
  refresh_token
}
canary() { # hello on a Celery worker, end to end
  local pod
  pod=$(run_hello)
  say "  canary: hello succeeded on $pod"
}
trigger_load() { # tasks seconds hold_mb -> run id
  api POST "/api/v2/dags/$LOAD/dagRuns" \
    "{\"logical_date\":null,\"conf\":{\"tasks\":$1,\"seconds\":$2,\"hold_mb\":$3}}" | jq -r .dag_run_id
}
keda_set_query() { # the worker ScaledObject's trigger query (the Airflow chart owns it; helm upgrade resets it)
  kc patch scaledobject airflow-worker --type json \
    -p "$(jq -nc --arg q "$1" '[{op: "replace", path: "/spec/triggers/0/metadata/query", value: $q}]')" >/dev/null 2>&1
}
# Pausing a ScaledObject at N replicas makes KEDA hold the workers there until the annotation goes.
keda_pause() { kc annotate scaledobject airflow-worker --overwrite "autoscaling.keda.sh/paused-replicas=$1" >/dev/null; }
keda_resume() { kc annotate scaledobject airflow-worker autoscaling.keda.sh/paused-replicas- >/dev/null; }
# shellcheck disable=SC2016 # $REDIS_PASSWORD expands inside the Redis container
redis_cli() { kc exec airflow-redis-0 -- sh -c 'redis-cli -a "$REDIS_PASSWORD" --no-auth-warning "$@"' redis-cli "$@"; }
restart_redis() { # the broker keeps no data (values.yaml), so every message it holds is dropped
  kc delete pod airflow-redis-0 --wait=true >/dev/null
  kc wait --for=condition=Ready pod/airflow-redis-0 --timeout=120s >/dev/null
}
trigger_hello() { # -> run id
  api PATCH /api/v2/dags/hello '{"is_paused":false}' >/dev/null
  api POST /api/v2/dags/hello/dagRuns '{"logical_date":null}' | jq -r .dag_run_id
}
hello_ti() { api GET "/api/v2/dags/hello/dagRuns/$1/taskInstances/say_hello" | jq -r "$2"; }
wait_hello() { # run timeout -> seconds until say_hello succeeded
  local end=$((SECONDS + $2)) start=$SECONDS state=""
  while [ $SECONDS -lt $end ]; do
    state=$(hello_ti "$1" .state)
    case "$state" in success) echo $((SECONDS - start)); return 0 ;; failed) fail "hello run $1 failed" ;; esac
    sleep 5
  done
  fail "hello run $1: say_hello still $state after $2 s"
}
worker_restarts() { kc get pods -l component=worker -o json | jq '[.items[].status.containerStatuses[] | select(.name=="worker") | .restartCount] | add // 0'; }
keda_ready() { kc get scaledobject airflow-worker -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'; }
run_state() { api GET "/api/v2/dags/$LOAD/dagRuns/$1" | jq -r .state; }
wait_run_done() { # run timeout -> final state
  local end=$((SECONDS + $2)) state=""
  while [ $SECONDS -lt $end ]; do
    state=$(run_state "$1")
    case "$state" in success | failed) echo "$state"; return 0 ;; esac
    sleep 5
  done
  fail "run $1 still $state after $2 s"
}
# Scheduler, triggerer, and dag-processor jobs as Airflow sees them (D31): a `running` row whose
# heartbeat is younger than the 30 s health-check threshold. The job's hostname is its pod's name.
live_jobs() { # job_type -> count
  psql_meta "SELECT count(*) FROM job WHERE job_type = '$1' AND state = 'running'
             AND latest_heartbeat > now() - interval '30 seconds'"
}
wait_live() { # job_type count timeout
  local end=$((SECONDS + $3))
  until [ "$(live_jobs "$1")" -ge "$2" ]; do
    [ $SECONDS -lt $end ] || fail "fewer than $2 live $1 after $3 s ($(live_jobs "$1"))"
    sleep 2
  done
}
job_pod() { # job_type -> the pod of one live job of that type
  psql_meta "SELECT hostname FROM job WHERE job_type = '$1' AND state = 'running'
             AND latest_heartbeat > now() - interval '30 seconds' ORDER BY id LIMIT 1"
}
job_of() { psql_meta "SELECT max(id) FROM job WHERE hostname = '$1' AND state = 'running'"; } # pod -> job id
job_host() { psql_meta "SELECT hostname FROM job WHERE id = $1"; } # job id -> pod
# The image has no kill(1). PID 1 is dumb-init; the job is the lowest-numbered `airflow <component>`
# process (a triggerer's trigger runner is its child). SIGKILL is a crash (the container restarts in
# place); SIGSTOP is a hang (the pod stays Running and stops heartbeating until it is deleted).
signal_job() { # pod container SIGKILL|SIGSTOP
  [ "$3" != SIGSTOP ] || hung=$1
  kc exec "$1" -c "$2" -- python -c "import os, signal; procs = [int(p) for p in os.listdir('/proc') if p.isdigit() and int(p) > 1]; os.kill(min(p for p in procs if b'airflow\0$2' in open(f'/proc/{p}/cmdline', 'rb').read()), signal.$3)" ||
    fail "could not send $3 to the $2 in $1"
}
ti_summary() { # load run -> task instance counts by state
  psql_meta "SELECT string_agg(state || '=' || n, ' ') FROM (SELECT coalesce(state, 'none') AS state, count(*) AS n
             FROM task_instance WHERE dag_id = '$LOAD' AND run_id = '$1' GROUP BY 1 ORDER BY 1) s"
}
restarts() { # pod=restarts for every Airflow pod that restarted at least once
  kc get pods -o json | jq -r '[.items[] | {n: .metadata.name, r: ([.status.containerStatuses[]?.restartCount] | add // 0)} | select(.r > 0) | "\(.n)=\(.r)"] | join(" ")'
}
restarted_since() { # restarts() snapshot -> pods that restarted after it
  local p
  for p in $(restarts); do
    case " $1 " in *" $p "*) ;; *) echo -n "$p " ;; esac
  done
}

# ---- preflight --------------------------------------------------------------------------------------
start_port_forward
refresh_token
start_prometheus
wait_ready
wait_dag_ready "$LOAD"
load_was_paused=$(api GET "/api/v2/dags/$LOAD" | jq -r .is_paused)
api PATCH "/api/v2/dags/$LOAD" '{"is_paused":false}' >/dev/null
pool_size 16
firing=$(firing_ours)
[ -z "$firing" ] || fail "alerts already firing before the drills: $firing"
canary
echo "ok: preflight: all components ready, no drill alert firing, canary passed"

# ---- 1. lose a scheduler ----------------------------------------------------------------------------
# Two schedulers (D31) share the work through row locks; losing one must not stop scheduling or run
# any task twice. 1a crashes one mid-run (the container restarts in place within seconds); 1b hangs
# one (a frozen process keeps its pod Running, so only the live-job count sees it) until
# AirflowSchedulerDegraded fires; 1c stops them all for AirflowSchedulerDown, as before (D28).
drill_1() {
  local run victim dead took health n t
  say "1a. scheduler: crash (SIGKILL) one of $SCHEDULERS while 16 tasks x 60 s are queued or running"
  run=$(trigger_load 16 60 0)
  end=$((SECONDS + 120))
  until [ "$(api GET "/api/v2/dags/$LOAD/dagRuns/$run/taskInstances?task_id=hold_slot&state=running" | jq -r .total_entries)" -gt 0 ]; do
    [ $SECONDS -lt $end ] || fail "no task of $run started"
    sleep 2
  done
  victim=$(job_pod SchedulerJob)
  dead=$(job_of "$victim")
  signal_job "$victim" scheduler SIGKILL
  t=$SECONDS
  say "  killed job $dead in $victim; $(ti_summary "$run")"
  [ "$(wait_run_done "$run" 600)" = success ] || fail "$run failed after a scheduler crash"
  n=$(psql_meta "SELECT count(*) FROM task_instance WHERE dag_id = '$LOAD' AND run_id = '$run' AND try_number <> 1")
  n=$((n + $(psql_meta "SELECT count(*) FROM task_instance_history WHERE dag_id = '$LOAD' AND run_id = '$run'")))
  say "  work kept moving: $run succeeded $((SECONDS - t))s after the kill; task instances past try 1 or with history: $n"
  [ "$n" = 0 ] || fail "a task of $run ran more than once after the scheduler crash"
  [ "$(psql_meta "SELECT end_date IS NULL FROM job WHERE id = $dead")" = t ] || fail "job $dead ended cleanly; the kill was not a crash"
  [ "$(alert_state AirflowSchedulerDown)" = inactive ] || fail "AirflowSchedulerDown fired with a scheduler left"
  wait_live SchedulerJob "$SCHEDULERS" 120
  echo "ok: (1a) scheduler crash mid-run: no stall, no task twice"

  say "1b. scheduler: hang (SIGSTOP) one of $SCHEDULERS"
  victim=$(job_pod SchedulerJob)
  signal_job "$victim" scheduler SIGSTOP
  took=$(wait_alert AirflowSchedulerDegraded firing 300)
  say "  detected: AirflowSchedulerDegraded firing after ${took}s (live $(live_jobs SchedulerJob) of $SCHEDULERS); $victim is still $(kc get pod "$victim" -o jsonpath='{.status.phase}')"
  [ "$(alert_state AirflowSchedulerDown)" = inactive ] || fail "AirflowSchedulerDown fired with a scheduler left"
  canary
  # Recovery: delete the hung pod; its liveness probe (airflow jobs check, 5 x 60 s) would restart
  # the container about 5 minutes into the hang otherwise.
  t=$SECONDS
  kc delete pod "$victim" --wait=true >/dev/null
  hung=""
  kc rollout status deploy/airflow-scheduler --timeout=300s >/dev/null
  wait_alert AirflowSchedulerDegraded inactive 300 >/dev/null
  say "  recovered: hung pod deleted, alert resolved $((SECONDS - t))s after the delete"
  canary
  echo "ok: (1b) hung scheduler detected and recovered"

  say "1c. scheduler: all $SCHEDULERS stopped (scaled to 0)"
  kc scale deploy/airflow-scheduler --replicas=0 >/dev/null
  kc wait --for=delete pod -l component=scheduler --timeout=120s >/dev/null 2>&1 || true
  took=$(wait_alert AirflowSchedulerDown firing 300)
  health=$(api GET /api/v2/monitor/health | jq -r '.scheduler.status')
  say "  detected: AirflowSchedulerDown firing after ${took}s; /monitor/health scheduler=$health"
  [ "$health" = unhealthy ] || fail "health endpoint reports scheduler '$health' while it is down"
  kc scale deploy/airflow-scheduler --replicas="$SCHEDULERS" >/dev/null
  kc rollout status deploy/airflow-scheduler --timeout=300s >/dev/null
  took=$(wait_alert AirflowSchedulerDown inactive 300)
  say "  recovered: schedulers back, alert resolved after ${took}s"
  canary
  echo "ok: (1c) scheduler outage detected and recovered"
}

# ---- 2. drain the worker's node ---------------------------------------------------------------------
drill_2() {
  node=$(kc get pod -l component=worker -o jsonpath='{.items[0].spec.nodeName}')
  say "2. drain: $node (runs $(kc get pods -o wide --no-headers --field-selector=status.phase=Running | awk -v n="$node" '$7==n{print $1}' | tr '\n' ' '))"
  bouncers=$(kc get pods -l component=pgbouncer -o wide --no-headers | awk -v n="$node" '$7==n' | wc -l)
  before=$(restarts)
  # Schedulers and triggerers run two replicas behind PDBs (D31): sample how many are live through
  # the drain; each role must keep at least one heartbeating job the whole time.
  samples=$(mktemp)
  (while :; do echo "$(live_jobs SchedulerJob) $(live_jobs TriggererJob)" >>"$samples"; sleep 2; done) &
  sampler=$!
  # Prometheus keeps its TSDB on a PVC on the control plane (D21, issue #9); remember a pre-drain sample.
  history_at=$(($(date +%s) - 30))
  history=$(prom_value_at 'count(up)' "$history_at")
  [ -n "$history" ] || fail "no count(up) sample at $history_at to check Prometheus' history against"
  kubectl --context "$CTX" drain "$node" --ignore-daemonsets --delete-emptydir-data --timeout=300s >/dev/null
  took=$(wait_alert KubeNodeUnschedulable firing 240)
  say "  detected: KubeNodeUnschedulable firing after ${took}s"
  wait_ready
  wait_api
  wait_live SchedulerJob "$SCHEDULERS" 180
  wait_live TriggererJob "$TRIGGERERS" 180
  kill "$sampler"
  sampler=""
  min_s=$(sort -n -k1,1 "$samples" | head -1 | cut -d' ' -f1) min_t=$(sort -n -k2,2 "$samples" | head -1 | cut -d' ' -f2)
  say "  live through the drain ($(wc -l <"$samples") samples): schedulers >= $min_s of $SCHEDULERS, triggerers >= $min_t of $TRIGGERERS"
  rm -f "$samples"
  [ "$min_s" -ge 1 ] || fail "no scheduler was live at some point of the drain"
  [ "$min_t" -ge 1 ] || fail "no triggerer was live at some point of the drain"
  pending=$(kc get pods --field-selector=status.phase=Pending --no-headers 2>/dev/null | wc -l)
  # Running pods only: a finished Job's pod (the DB cleanup CronJob's) may stay on the node.
  on_node=$(kc get pods -o wide --no-headers --field-selector=status.phase=Running | awk -v n="$node" '$7==n' | wc -l)
  say "  every Airflow component rescheduled: $on_node pods left on $node, $pending Pending"
  [ "$on_node" = 0 ] && [ "$pending" = 0 ] || fail "pods still on $node ($on_node) or Pending ($pending)"
  canary
  # PgBouncer runs two replicas behind a PDB, so moving one must not cost any component its DB.
  restarted=$(restarted_since "$before")
  say "  $bouncers of $(kc get pods -l component=pgbouncer --no-headers | wc -l) PgBouncer replicas moved; restarted during the drain: [${restarted:-none}]"
  [ -z "$restarted" ] || fail "containers restarted during the drain: $restarted"
  kubectl --context "$CTX" uncordon "$node" >/dev/null
  took=$(wait_alert KubeNodeUnschedulable inactive 240)
  say "  recovered: $node uncordoned, alert resolved after ${took}s"
  canary
  # A drain never reaches Prometheus (it stays on the control plane with its node-pinned volume), so
  # restart it the way an eviction would and check the history from before the drain is still there.
  kubectl --context "$CTX" -n monitoring delete pod prometheus-kps-prometheus-0 --wait=true >/dev/null
  start_prometheus
  prom_node=$(kubectl --context "$CTX" -n monitoring get pod prometheus-kps-prometheus-0 -o jsonpath='{.spec.nodeName}')
  kept=$(prom_value_at 'count(up)' "$history_at")
  say "  Prometheus restarted on $prom_node: count(up) at $(date -d "@$history_at" +%T) was $history, now reads ${kept:-nothing}"
  [ "$kept" = "$history" ] || fail "Prometheus lost its history across a restart ($history -> ${kept:-nothing})"
  echo "ok: (2) node drain detected; workloads moved off the node and kept running; Prometheus kept its history"
}

# ---- 3. stop the metadata DB ------------------------------------------------------------------------
drill_3() {
  before=$(restarts)
  say "3. metadata DB: docker compose stop metadata-db"
  "${COMPOSE[@]}" stop metadata-db >/dev/null
  took=$(wait_alert MetadataDBDown firing 180)
  say "  detected: MetadataDBDown firing after ${took}s"
  took=$(wait_alert AirflowSchedulerDown firing 300)
  say "  the scheduler lost its heartbeat too: AirflowSchedulerDown firing after ${took}s more"
  "${COMPOSE[@]}" start metadata-db >/dev/null
  "${COMPOSE[@]}" up -d --wait metadata-db >/dev/null
  took=$(wait_alert MetadataDBDown inactive 180)
  say "  DB back; MetadataDBDown resolved after ${took}s"
  wait_ready
  wait_api
  took=$(wait_alert AirflowSchedulerDown inactive 600)
  say "  scheduler heartbeating again after ${took}s; restarted pods before: [${before:-none}] after: [$(restarts)]"
  canary
  echo "ok: (3) metadata DB outage detected and recovered"
}

# ---- 4a. slot starvation ----------------------------------------------------------------------------
drill_4a() {
  say "4a. slots: pool ops_load shrunk to 1, then 4 tasks x 60 s"
  pool_size 1
  run=$(trigger_load 4 60 0)
  took=$(wait_alert AirflowPoolStarving firing 240)
  starving=$(prom_value 'max(airflow_pool_starving_tasks{pool_name="ops_load"})')
  say "  detected: AirflowPoolStarving firing after ${took}s (ops_load starving tasks: $starving)"
  pool_size 16
  took=$(wait_alert AirflowPoolStarving inactive 300)
  say "  recovered: pool back to 16, alert resolved after ${took}s"
  [ "$(wait_run_done "$run" 600)" = success ] || fail "load run $run failed after the pool was restored"
  say "  the backlog drained: $run succeeded"
  echo "ok: (4a) slot starvation detected and recovered"
}

# ---- 4b. memory starvation --------------------------------------------------------------------------
drill_4b() {
  limit=$(kc get deploy airflow-worker -o jsonpath='{.spec.template.spec.containers[?(@.name=="worker")].resources.limits.memory}')
  say "4b. memory: one task holds 1700 MiB on a worker limited to $limit"
  run=$(trigger_load 1 60 1700)
  took=$(wait_alert AirflowContainerOOMKilled firing 300)
  say "  detected: AirflowContainerOOMKilled firing after ${took}s"
  state=$(wait_run_done "$run" 600)
  ti=$(api GET "/api/v2/dags/$LOAD/dagRuns/$run/taskInstances?task_id=hold_slot" | jq -c '.task_instances[0] | {state, try_number}')
  say "  the task that exceeded the limit: $ti (run $state; retries=0 by design)"
  [ "$state" = failed ] || fail "the over-limit task did not fail ($state)"
  wait_ready
  canary
  took=$(wait_alert AirflowContainerOOMKilled inactive 600)
  say "  recovered: worker restarted by the kubelet, alert resolved after ${took}s"
  echo "ok: (4b) worker OOMKill detected and recovered"
}

# ---- 7. break KEDA's worker scaler ------------------------------------------------------------------
# Stands in for any scaler fault (DB credentials, PgBouncer, the prepared-statement clash of issue #7):
# the HPA cannot read its metric and keeps the current worker count.
drill_7() {
  keda_query=$(kc get scaledobject airflow-worker -o jsonpath='{.spec.triggers[0].metadata.query}')
  workers=$(kc get deploy airflow-worker -o jsonpath="{.spec.replicas}")
  say "7. KEDA: the worker trigger's query now reads a table that does not exist ($workers workers)"
  keda_set_query "SELECT count(*) FROM pplk8s_no_such_table"
  took=$(wait_alert KedaScalerErrors firing 300)
  failed=$(prom_value 'sum(increase(keda_scaled_object_errors_total{scaledObject="airflow-worker"}[1m]))')
  hpa=$(kc get hpa keda-hpa-airflow-worker -o jsonpath='{.status.conditions[?(@.type=="ScalingActive")].reason}')
  say "  detected: KedaScalerErrors firing after ${took}s (${failed%.*} failed polls in the last minute); ScaledObject Ready=$(keda_ready), HPA ScalingActive=$hpa"
  [ "$(kc get deploy airflow-worker -o jsonpath="{.spec.replicas}")" = "$workers" ] ||
    fail "the worker count moved while the scaler was failing"
  keda_set_query "$keda_query"
  keda_query=""
  took=$(wait_alert KedaScalerErrors inactive 300)
  [ "$(keda_ready)" = True ] || fail "ScaledObject airflow-worker not Ready after the query was restored"
  say "  recovered: query restored, ScaledObject Ready, alert resolved after ${took}s"
  canary
  echo "ok: (7) KEDA scaler failure detected and recovered"
}

# ---- 8. restart the Celery broker -------------------------------------------------------------------
# The broker (the chart's Redis) keeps no data, so a restart drops every message it holds; Celery
# workers reconnect within seconds. A message waiting in Redis is lost (8a). A worker that had a
# task running when the connection dropped used to take no new task until that task ended, or
# block in a dead socket read until its liveness probe killed it and the task (issue #15); the
# Redis socket timeout and the busy-worker backport (pplk8s.celery_config) fix both (8b).
drill_8() {
  say "8a. broker: restart Redis while a task waits in it for a worker"
  keda_pause 0
  kc wait --for=delete pod -l component=worker --timeout=180s >/dev/null 2>&1 || true
  h=$(trigger_hello)
  end=$((SECONDS + 120))
  until [ "$(hello_ti "$h" .state)" = queued ] || [ $SECONDS -ge $end ]; do sleep 2; done
  waiting=$(redis_cli llen default)
  say "  no worker; say_hello is $(hello_ti "$h" .state) and Redis holds $waiting message(s) in queue 'default'"
  [ "$(hello_ti "$h" .state)" = queued ] && [ "$waiting" -ge 1 ] || fail "say_hello is not waiting in the broker"
  restart_redis
  say "  Redis restarted: queue 'default' now holds $(redis_cli llen default) message(s)"
  keda_resume
  kc rollout status deploy/airflow-worker --timeout=300s >/dev/null
  took=$(wait_alert AirflowTasksStuckQueued firing 420)
  say "  detected: AirflowTasksStuckQueued firing after ${took}s; a worker is up, and say_hello is still $(hello_ti "$h" .state)"
  [ "$(hello_ti "$h" .state)" = queued ] || fail "say_hello left queued without a message"
  # Recovery: clear the stuck task instance; otherwise the scheduler requeues it after task_queued_timeout.
  api POST /api/v2/dags/hello/clearTaskInstances \
    "{\"dry_run\":false,\"dag_run_id\":\"$h\",\"task_ids\":[\"say_hello\"],\"only_failed\":false}" >/dev/null
  took=$(wait_hello "$h" 180)
  say "  recovered: say_hello cleared, then succeeded after ${took}s (try $(hello_ti "$h" .try_number))"
  took=$(wait_alert AirflowTasksStuckQueued inactive 180)
  say "  alert resolved after ${took}s"
  echo "ok: (8a) lost broker message detected and recovered"

  say "8b. broker: restart Redis while a worker runs a task"
  end=$((SECONDS + 300))
  until [ "$(kc get pods -l component=worker --no-headers | wc -l)" = 1 ] || [ $SECONDS -ge $end ]; do sleep 5; done
  run=$(trigger_load 1 240 0)
  end=$((SECONDS + 180))
  until [ "$(api GET "/api/v2/dags/$LOAD/dagRuns/$run/taskInstances?task_id=hold_slot" | jq -r '.task_instances[0].state')" = running ] || [ $SECONDS -ge $end ]; do sleep 3; done
  restarts_before=$(worker_restarts)
  restart_redis
  h=$(trigger_hello)
  say "  Redis restarted under a 240 s task; hello triggered"
  took=$(wait_hello "$h" 60)
  restarted=$(($(worker_restarts) - restarts_before))
  say "  say_hello succeeded ${took}s after the restart, beside the running task; worker containers restarted: $restarted"
  [ "$restarted" -eq 0 ] || fail "a worker was restarted after the broker restart (stuck in a dead socket read?)"
  state=$(wait_run_done "$run" 600)
  say "  the 240 s task that ran through the broker restart: $state"
  [ "$state" = success ] || fail "the task that ran through the broker restart ended $state"
  canary
  echo "ok: (8b) broker restart under a running task recovered"
}

# ---- 9. lose a triggerer while a readiness wait is deferred -----------------------------------------
# finance_daily's waits defer to ReadinessTrigger, which polls ops.readiness from a triggerer (D19).
# A trigger belongs to one triggerer job; another triggerer claims it only once that job has ended
# (a clean stop) or its heartbeat is older than triggerer_health_check_threshold (a crash or a
# hang). With two triggerers (D31) the survivor takes over a lost one's triggers (9a: hang, 9b:
# crash); with none, the waits stay deferred until one returns (9c). Each upstream is marked ready
# while its wait's triggerer is gone: the wait must resume with no retry (issues #17, #20). The
# interval is one no producer builds; its ledger rows are the drill's own (run_id phase6-check).
FIN_START='2026-09-30 00:00:00+00' FIN_END='2026-10-01 00:00:00+00'
fin_ti() { api GET "/api/v2/dags/$FIN/dagRuns/$1/taskInstances/$2" | jq -r .state; }
fin_ready() { # product: stand in for its producer finishing the interval
  psql_wh "INSERT INTO ops.readiness (product, interval_start, interval_end, watermark, run_id, status)
           VALUES ('$1', '$FIN_START', '$FIN_END', '$FIN_END', 'phase6-check', 'ready')" >/dev/null
}
trigger_owner() { # run task -> id of the triggerer job holding the task's trigger (empty once fired)
  psql_meta "SELECT t.triggerer_id FROM task_instance ti JOIN trigger t ON t.id = ti.trigger_id
             WHERE ti.dag_id = '$FIN' AND ti.run_id = '$1' AND ti.task_id = '$2'"
}
wait_new_owner() { # run task old-job timeout -> waits until another job holds the trigger; prints its id
  local end=$((SECONDS + $4)) new
  while new=$(trigger_owner "$1" "$2"); [ "$new" = "$3" ]; do
    [ $SECONDS -lt $end ] || fail "no triggerer claimed the trigger of $2 from job $3 within $4 s"
    sleep 1
  done
  [ -n "$new" ] || fail "the trigger of $2 disappeared (its upstream is not ready)"
  echo "$new"
}
wait_fin_ti() { # run task timeout -> seconds until the task succeeded
  local end=$((SECONDS + $3)) start=$SECONDS state=""
  while [ $SECONDS -lt $end ]; do
    state=$(fin_ti "$1" "$2")
    case "$state" in success) echo $((SECONDS - start)); return 0 ;; failed | up_for_retry) fail "$2 in $1 is $state" ;; esac
    sleep 1
  done
  fail "$2 in $1 still $state after $3 s"
}
heartbeat_age() { psql_meta "SELECT round(extract(epoch FROM now() - latest_heartbeat)) FROM job WHERE id = $1"; }

drill_9() {
  local in_interval real fin_run threshold old new owner victim survivor t took stale state slots ready n
  wait_dag_ready "$FIN"
  fin_was_paused=$(api GET "/api/v2/dags/$FIN" | jq -r .is_paused)
  api PATCH "/api/v2/dags/$FIN" '{"is_paused":false}' >/dev/null
  in_interval="interval_start = '$FIN_START' AND interval_end = '$FIN_END'"
  psql_wh "DELETE FROM ops.readiness WHERE $in_interval AND (run_id = 'phase6-check' OR product = 'finance.exposed')" >/dev/null
  real=$(psql_wh "SELECT string_agg(product || ' by ' || run_id, ', ') FROM ops.readiness WHERE $in_interval")
  [ -z "$real" ] || fail "the drill's interval [$FIN_START, $FIN_END) already has producer rows: $real"
  fin_run="phase6__triggerer__$(date +%s)"
  api POST "/api/v2/dags/$FIN/dagRuns" \
    "{\"dag_run_id\":\"$fin_run\",\"logical_date\":\"2026-10-01T00:00:00.$(date +%N | cut -c1-6)Z\"}" >/dev/null ||
    fail "could not trigger $FIN"
  end=$((SECONDS + 180))
  until [ "$(fin_ti "$fin_run" wait_sales_gold)" = deferred ] && [ "$(fin_ti "$fin_run" wait_returns_silver)" = deferred ]; do
    [ $SECONDS -lt $end ] || fail "the waits of $fin_run never deferred"
    sleep 3
  done
  threshold=$(kc exec deploy/airflow-triggerer -c triggerer -- airflow config get-value triggerer triggerer_health_check_threshold 2>/dev/null | tail -1)
  say "9. $fin_run: both waits deferred, on triggerer jobs $(trigger_owner "$fin_run" wait_sales_gold) and $(trigger_owner "$fin_run" wait_returns_silver) (of $TRIGGERERS triggerers)"

  say "9a. triggerer: hang (SIGSTOP) the one holding wait_sales_gold; sales.gold marked ready meanwhile"
  old=$(trigger_owner "$fin_run" wait_sales_gold)
  [ -n "$old" ] || fail "wait_sales_gold's trigger is not assigned to a triggerer"
  victim=$(job_host "$old")
  # Hang first, then hold the wait's upstream back until the takeover is seen: a trigger that fires
  # at once would leave no owner to watch. returns.silver stays unready, so its trigger stays put.
  signal_job "$victim" triggerer SIGSTOP
  t=$SECONDS
  new=$(wait_new_owner "$fin_run" wait_sales_gold "$old" 180)
  took=$((SECONDS - t)) stale=$(heartbeat_age "$old") survivor=$(job_host "$new")
  say "  taken over by job $new on $survivor ${took}s after the hang; the hung job $old last heartbeated ${stale}s ago (threshold ${threshold}s)"
  [ "$survivor" != "$victim" ] || fail "the hung pod $victim claimed its own trigger"
  [ "$stale" -ge "$threshold" ] || fail "job $new claimed the trigger before job $old's heartbeat was $threshold s stale"
  fin_ready sales.gold
  took=$(wait_fin_ti "$fin_run" wait_sales_gold 60)
  say "  wait_sales_gold succeeded ${took}s after sales.gold turned ready (try $(api GET "/api/v2/dags/$FIN/dagRuns/$fin_run/taskInstances/wait_sales_gold" | jq -r .try_number))"
  took=$(wait_alert AirflowTriggererDegraded firing 300)
  say "  detected: AirflowTriggererDegraded firing $((SECONDS - t))s after the hang (live $(live_jobs TriggererJob) of $TRIGGERERS); AirflowTriggererDown $(alert_state AirflowTriggererDown)"
  [ "$(alert_state AirflowTriggererDown)" = inactive ] || fail "AirflowTriggererDown fired with a triggerer left"
  t=$SECONDS
  # A stopped process cannot act on SIGTERM, so the delete takes the full grace period (60 s).
  kc delete pod "$victim" --wait=true >/dev/null
  hung=""
  kc rollout status deploy/airflow-triggerer --timeout=180s >/dev/null
  wait_live TriggererJob "$TRIGGERERS" 120
  wait_alert AirflowTriggererDegraded inactive 300 >/dev/null
  say "  recovered: hung pod deleted, $TRIGGERERS triggerers live and the alert resolved $((SECONDS - t))s after the delete"
  echo "ok: (9a) hung triggerer: the survivor took over the deferred wait"

  say "9b. triggerer: crash (SIGKILL) the one holding wait_returns_silver"
  old=$(trigger_owner "$fin_run" wait_returns_silver)
  [ -n "$old" ] || fail "wait_returns_silver's trigger is not assigned to a triggerer"
  victim=$(job_host "$old")
  signal_job "$victim" triggerer SIGKILL
  t=$SECONDS
  new=$(wait_new_owner "$fin_run" wait_returns_silver "$old" 180)
  took=$((SECONDS - t)) stale=$(heartbeat_age "$old") owner=$(job_host "$new")
  [ "$owner" = "$victim" ] && owner="$owner (the crashed pod's restarted container)" || owner="$owner (the other triggerer)"
  say "  claimed by job $new on $owner ${took}s after the kill, at a dead-job heartbeat age of ${stale}s"
  [ "$(psql_meta "SELECT end_date IS NULL FROM job WHERE id = $old")" = t ] || fail "job $old ended cleanly; the kill was not a crash"
  [ "$stale" -ge "$threshold" ] || fail "job $new claimed the trigger before job $old's heartbeat was $threshold s stale"
  [ "$(fin_ti "$fin_run" wait_returns_silver)" = deferred ] || fail "wait_returns_silver left deferred without its upstream"
  [ "$(alert_state AirflowTriggererDown)" = inactive ] || fail "AirflowTriggererDown fired with a triggerer left"
  wait_live TriggererJob "$TRIGGERERS" 120
  echo "ok: (9b) triggerer crash under a deferred wait: the trigger moved once"

  say "9c. triggerer: all $TRIGGERERS stopped (scaled to 0) while wait_returns_silver is deferred; returns.silver marked ready meanwhile"
  old=$new
  kc scale deploy/airflow-triggerer --replicas=0 >/dev/null
  kc wait --for=delete pod -l component=triggerer --timeout=120s >/dev/null
  [ "$(psql_meta "SELECT end_date IS NOT NULL FROM job WHERE id = $old")" = t ] || fail "job $old did not end on SIGTERM"
  fin_ready returns.silver
  took=$(wait_alert AirflowTriggererDown firing 300)
  state=$(fin_ti "$fin_run" wait_returns_silver)
  slots=$(api GET /api/v2/pools/default_pool | jq -r '"running=\(.running_slots) deferred=\(.deferred_slots)"')
  say "  detected: AirflowTriggererDown firing after ${took}s; wait_returns_silver is $state with its upstream ready; default_pool $slots"
  [ "$state" = deferred ] || fail "wait_returns_silver is $state without a triggerer"
  [ "$(trigger_owner "$fin_run" wait_returns_silver)" = "$old" ] || fail "the trigger left the stopped job $old"
  kc scale deploy/airflow-triggerer --replicas="$TRIGGERERS" >/dev/null
  t=$SECONDS
  kc rollout status deploy/airflow-triggerer --timeout=180s >/dev/null
  ready=$((SECONDS - t))
  took=$(wait_fin_ti "$fin_run" wait_returns_silver 120)
  say "  recovered: triggerers Ready ${ready}s after the scale-up; wait_returns_silver succeeded $((ready + took))s after the scale-up"
  took=$(wait_alert AirflowTriggererDown inactive 180)
  say "  alert resolved after ${took}s"
  end=$((SECONDS + 600))
  until state=$(api GET "/api/v2/dags/$FIN/dagRuns/$fin_run" | jq -r .state) && [ "$state" != running ] && [ "$state" != queued ]; do
    [ $SECONDS -lt $end ] || fail "$fin_run still $state after 600 s"
    sleep 5
  done
  [ "$state" = success ] || fail "$fin_run ended $state"
  [ "$(psql_wh "SELECT status FROM ops.readiness WHERE product = 'finance.exposed' AND $in_interval")" = ready ] ||
    fail "finance.exposed is not recorded for the drill's interval"
  n=$(psql_meta "SELECT count(*) FROM task_instance WHERE dag_id = '$FIN' AND run_id = '$fin_run' AND try_number <> 1")
  [ "$n" = 0 ] || fail "$n task(s) of $fin_run needed a retry"
  say "  $fin_run succeeded on try 1 throughout and recorded finance.exposed"
  canary
  echo "ok: (9c) triggerer outage under a deferred wait detected and recovered"
}

# ---- 11. git-sync cannot fetch ------------------------------------------------------------------------
# Every pod that loads DAG files runs a git-sync sidecar (D23). A fetch that fails after a good sync (a
# deleted ref, a revoked deploy key, GitHub unreachable) leaves it retrying (maxFailures -1) on its
# last good commit, Running and Ready, so DAG changes silently stop arriving (#18). The drill makes
# GitHub unreachable over SSH for those pods with a NetworkPolicy (every other egress port stays open)
# and expects AirflowGitSyncFailing for each of them while every pod stays Ready and nothing restarts.
GIT_PODS='tier=airflow,component in (dag-processor,triggerer,worker)'
block_git_ssh() {
  git_blocked=1
  kc apply -f - >/dev/null <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: drill-block-git-ssh}
spec:
  podSelector:
    matchExpressions: [{key: component, operator: In, values: [dag-processor, triggerer, worker]}]
  policyTypes: [Egress]
  egress:
    - ports: # everything but TCP 22
        - {protocol: TCP, port: 1, endPort: 21}
        - {protocol: TCP, port: 23, endPort: 65535}
        - {protocol: UDP, port: 1, endPort: 65535}
EOF
}
git_pods() { kc get pods -l "$GIT_PODS" --field-selector=status.phase=Running -o name | wc -l; }
synced_pods() { prom_value 'count(count by (pod) (increase(git_sync_count_total{status=~"success|noop"}[1m]) > 0))'; }
ready_pods() { kc get pods -l "$GIT_PODS" -o json | jq '[.items[] | select(all(.status.containerStatuses[]; .ready))] | length'; }
drill_11() {
  local pods before took t firing err end
  if ! kc get deploy airflow-dag-processor -o jsonpath='{.spec.template.spec.containers[*].name}' | grep -qw git-sync; then
    say "11. skipped: DAGs come from the host-path mount, not git-sync (DAG_DELIVERY=local)"
    return 0
  fi
  pods=$(git_pods)
  [ "$(synced_pods)" = "$pods" ] || fail "only $(synced_pods) of $pods git-sync sidecars report syncs before the drill"
  before=$(restarts)
  say "11. git-sync: block SSH egress (GitHub) for the $pods pods that sync DAGs"
  block_git_ssh
  t=$SECONDS
  took=$(wait_alert AirflowGitSyncFailing firing 420)
  end=$((SECONDS + 120))
  until firing=$(prom 'ALERTS{alertname="AirflowGitSyncFailing", alertstate="firing"}' | jq length) && [ "$firing" = "$pods" ]; do
    [ $SECONDS -lt $end ] || fail "AirflowGitSyncFailing fires for $firing of $pods pods"
    sleep 5
  done
  err=$(kc logs deploy/airflow-dag-processor -c git-sync --since=5m | grep -o 'error syncing repo, will retry' | tail -1 || true)
  say "  detected: AirflowGitSyncFailing firing for $firing of $pods pods $((SECONDS - t))s after the block; $(ready_pods) of $pods pods Ready; git-sync: ${err:-no retry line}"
  [ "$(ready_pods)" = "$pods" ] || fail "a pod went unready: the failure is not silent, so the drill no longer tests #18"
  [ -z "$(restarted_since "$before")" ] || fail "pods restarted while git-sync could not fetch: $(restarted_since "$before")"
  [ "$(alert_state AirflowComponentUnavailable)" = inactive ] || fail "AirflowComponentUnavailable fired; the pods should look healthy"
  # Recovery (runbook drill 11): make the remote reachable again; git-sync resumes on its next period.
  t=$SECONDS
  kc delete networkpolicy drill-block-git-ssh >/dev/null
  git_blocked=""
  took=$(wait_alert AirflowGitSyncFailing inactive 300)
  say "  recovered: SSH unblocked, alert resolved $((SECONDS - t))s later"
  canary
  echo "ok: (11) git-sync fetch failure detected and recovered"
}

# ---- run the drills -----------------------------------------------------------------------------------
# DRILLS="1 9" runs a subset (the preflight always runs); the default is every drill, in this order.
for d in ${DRILLS:-1 2 3 4a 4b 7 8 9 11}; do
  declare -F "drill_$d" >/dev/null || fail "no drill $d (DRILLS=$DRILLS)"
  "drill_$d"
done

firing=$(firing_ours)
[ -z "$firing" ] || fail "alerts still firing after the drills: $firing"
echo "phase6-check passed"
