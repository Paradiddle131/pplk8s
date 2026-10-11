#!/usr/bin/env bash
# Phase 6 exit check (PLAN.md D28): every failure drill is detected by a firing Prometheus alert and
# recovered by its docs/runbook.md procedure, proven by the alert resolving and a canary DAG run.
#   1  kill the scheduler (sustained: scaled to 0)      -> AirflowSchedulerDown
#   2  drain the node that runs the Celery worker       -> KubeNodeUnschedulable
#      (then restart Prometheus: its history from before the drain must survive)
#   3  stop the metadata DB                              -> MetadataDBDown
#   4a starve pool ops_load of slots                     -> AirflowPoolStarving
#   4b starve a worker of memory (a task over its limit) -> AirflowContainerOOMKilled
#   7  break KEDA's worker scaler (a query that fails)   -> KedaScalerErrors
#   8a restart the Celery broker holding a queued task   -> AirflowTasksStuckQueued (message lost)
#   8b restart the Celery broker while a task runs       -> new work waits for the running task (or a probe restart)
# The chart and Airflow minor roll lives in phase6-upgrade-drill.sh (it reinstalls Airflow).
# Expects `make airflow-up observability-up`. Re-runnable and self-restoring: the exit trap (also on
# SIGINT/SIGTERM) scales the scheduler back, starts the DB, uncordons nodes, and restores the pool,
# KEDA's query, and KEDA's scaling of the workers.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
source "$(dirname "$0")/lib/airflow-api.sh"
source "$(dirname "$0")/lib/prometheus.sh"
COMPOSE=(docker compose -f "$REPO/platform/compose/compose.yaml")
LOAD=ops_load_test
OUR_ALERTS='Airflow.*|MetadataDB.*|KubeNode.*|Keda.*'
say() { echo "[$(date +%T)] $*"; }

# ---- restorable state -------------------------------------------------------------------------------
load_was_paused="" keda_query=""
cleanup() {
  local rc=$? node
  set +e
  kc scale deploy/airflow-scheduler --replicas=1 >/dev/null 2>&1
  "${COMPOSE[@]}" start metadata-db >/dev/null 2>&1
  for node in $(kubectl --context "$CTX" get nodes -o jsonpath='{range .items[?(@.spec.unschedulable==true)]}{.metadata.name}{" "}{end}'); do
    kubectl --context "$CTX" uncordon "$node" >/dev/null && echo "uncordoned $node"
  done
  pool_size 16 >/dev/null 2>&1
  [ -z "$keda_query" ] || keda_set_query "$keda_query" >/dev/null 2>&1
  keda_resume >/dev/null 2>&1
  [ "$load_was_paused" = true ] && api PATCH "/api/v2/dags/$LOAD" '{"is_paused":true}' >/dev/null 2>&1
  stop_prometheus
  stop_port_forward
  exit $rc
}
trap cleanup EXIT

# ---- helpers ----------------------------------------------------------------------------------------
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

# ---- 1. kill the scheduler --------------------------------------------------------------------------
say "1. scheduler: scaled to 0 (a killed pod restarts within seconds, faster than any alert window)"
kc scale deploy/airflow-scheduler --replicas=0 >/dev/null
kc wait --for=delete pod -l component=scheduler --timeout=120s >/dev/null 2>&1 || true
took=$(wait_alert AirflowSchedulerDown firing 300)
health=$(api GET /api/v2/monitor/health | jq -r '.scheduler.status')
say "  detected: AirflowSchedulerDown firing after ${took}s; /monitor/health scheduler=$health"
[ "$health" = unhealthy ] || fail "health endpoint reports scheduler '$health' while it is down"
kc scale deploy/airflow-scheduler --replicas=1 >/dev/null
kc rollout status deploy/airflow-scheduler --timeout=300s >/dev/null
took=$(wait_alert AirflowSchedulerDown inactive 300)
say "  recovered: scheduler back, alert resolved after ${took}s"
canary
echo "ok: (1) scheduler outage detected and recovered"

# ---- 2. drain the worker's node ---------------------------------------------------------------------
node=$(kc get pod -l component=worker -o jsonpath='{.items[0].spec.nodeName}')
say "2. drain: $node (runs $(kc get pods -o wide --no-headers --field-selector=status.phase=Running | awk -v n="$node" '$7==n{print $1}' | tr '\n' ' '))"
bouncers=$(kc get pods -l component=pgbouncer -o wide --no-headers | awk -v n="$node" '$7==n' | wc -l)
before=$(restarts)
# Prometheus keeps its TSDB on a PVC on the control plane (D21, issue #9); remember a pre-drain sample.
history_at=$(($(date +%s) - 30))
history=$(prom_value_at 'count(up)' "$history_at")
[ -n "$history" ] || fail "no count(up) sample at $history_at to check Prometheus' history against"
kubectl --context "$CTX" drain "$node" --ignore-daemonsets --delete-emptydir-data --timeout=300s >/dev/null
took=$(wait_alert KubeNodeUnschedulable firing 240)
say "  detected: KubeNodeUnschedulable firing after ${took}s"
wait_ready
wait_api
pending=$(kc get pods --field-selector=status.phase=Pending --no-headers 2>/dev/null | wc -l)
on_node=$(kc get pods -o wide --no-headers | awk -v n="$node" '$7==n' | wc -l)
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

# ---- 3. stop the metadata DB ------------------------------------------------------------------------
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

# ---- 4a. slot starvation ----------------------------------------------------------------------------
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

# ---- 4b. memory starvation --------------------------------------------------------------------------
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

# ---- 7. break KEDA's worker scaler ------------------------------------------------------------------
# Stands in for any scaler fault (DB credentials, PgBouncer, the prepared-statement clash of issue #7):
# the HPA cannot read its metric and keeps the current worker count.
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

# ---- 8. restart the Celery broker -------------------------------------------------------------------
# The broker (the chart's Redis) keeps no data, so a restart drops every message it holds; Celery
# workers reconnect within seconds. Two cases differ: a message waiting in Redis is lost, and a
# worker that had a task running when the connection dropped takes no new task until that task
# ends, or, when it also stops answering pings, until its liveness probe restarts it (issue #15).
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
took=$(wait_hello "$h" 300)
restarted=$(($(worker_restarts) - restarts_before))
stuck=$(alert_state AirflowTasksStuckQueued)
say "  say_hello succeeded ${took}s after the restart (AirflowTasksStuckQueued: $stuck); worker containers restarted by their liveness probe: $restarted"
state=$(wait_run_done "$run" 600)
say "  the 240 s task that ran through the broker restart: $state (retries=0 by design; a probe restart kills it)"
if [ "$stuck" != inactive ]; then
  took=$(wait_alert AirflowTasksStuckQueued inactive 300)
  say "  AirflowTasksStuckQueued resolved after ${took}s more"
fi
canary
echo "ok: (8b) broker restart under a running task recovered"

firing=$(firing_ours)
[ -z "$firing" ] || fail "alerts still firing after the drills: $firing"
echo "phase6-check passed"
