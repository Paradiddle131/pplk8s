#!/usr/bin/env bash
# Phase 6 exit check (PLAN.md D28): every failure drill is detected by a firing Prometheus alert and
# recovered by its docs/runbook.md procedure, proven by the alert resolving and a canary DAG run.
#   1  kill the scheduler (sustained: scaled to 0)      -> AirflowSchedulerDown
#   2  drain the node that runs the Celery worker       -> KubeNodeUnschedulable
#   3  stop the metadata DB                              -> MetadataDBDown
#   4a starve pool ops_load of slots                     -> AirflowPoolStarving
#   4b starve a worker of memory (a task over its limit) -> AirflowContainerOOMKilled
# The chart and Airflow minor roll lives in phase6-upgrade-drill.sh (it reinstalls Airflow).
# Expects `make airflow-up observability-up`. Re-runnable and self-restoring: the exit trap (also on
# SIGINT/SIGTERM) scales the scheduler back, starts the DB, uncordons nodes, and restores the pool.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
source "$(dirname "$0")/lib/airflow-api.sh"
source "$(dirname "$0")/lib/prometheus.sh"
COMPOSE=(docker compose -f "$REPO/platform/compose/compose.yaml")
LOAD=ops_load_test
OUR_ALERTS='Airflow.*|MetadataDB.*|KubeNode.*'
say() { echo "[$(date +%T)] $*"; }

# ---- restorable state -------------------------------------------------------------------------------
load_was_paused=""
cleanup() {
  local rc=$? node
  set +e
  kc scale deploy/airflow-scheduler --replicas=1 >/dev/null 2>&1
  "${COMPOSE[@]}" start metadata-db >/dev/null 2>&1
  for node in $(kubectl --context "$CTX" get nodes -o jsonpath='{range .items[?(@.spec.unschedulable==true)]}{.metadata.name}{" "}{end}'); do
    kubectl --context "$CTX" uncordon "$node" >/dev/null && echo "uncordoned $node"
  done
  pool_size 16 >/dev/null 2>&1
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
echo "ok: (2) node drain detected; workloads moved off the node and kept running"

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

firing=$(firing_ours)
[ -z "$firing" ] || fail "alerts still firing after the drills: $firing"
echo "phase6-check passed"
