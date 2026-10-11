#!/usr/bin/env bash
# KEDA check (PLAN.md D24): a burst of ops_load_test tasks scales the Celery workers from the
# minimum out to more than one replica, every task succeeds on its first try (no task killed by a
# scale-in), and the workers scale back to the minimum after the cooldown. Then a forced scale-in
# while a task runs: a task shorter than the worker's grace period finishes during Celery's warm
# shutdown, and a longer one is killed and failed by the heartbeat timeout. Expects `make airflow-up`
# (KEDA on). Re-runnable: each run is new; the DAG's paused flag and KEDA's minimum are restored on exit.
set -euo pipefail

source "$(dirname "$0")/lib/airflow-api.sh"
DAG=ops_load_test
TASKS=${TASKS:-16}
SECONDS_PER_TASK=${SECONDS_PER_TASK:-45}
say() { echo "[$(date +%T)] $*"; }
replicas() { kc get deploy airflow-worker -o jsonpath='{.status.availableReplicas}'; }
desired() { kc get hpa keda-hpa-airflow-worker -o jsonpath='{.status.desiredReplicas}'; }

was_paused="" min=""
cleanup() {
  local rc=$?
  set +e
  [ -z "$min" ] || kc patch scaledobject airflow-worker --type merge \
    -p "{\"spec\":{\"minReplicaCount\":$min}}" >/dev/null 2>&1
  [ "$was_paused" = true ] && api PATCH "/api/v2/dags/$DAG" '{"is_paused":true}' >/dev/null
  stop_port_forward
  exit $rc
}
trap cleanup EXIT

start_port_forward
refresh_token
wait_dag_ready "$DAG"
min=$(kc get scaledobject airflow-worker -o jsonpath='{.spec.minReplicaCount}')
max=$(kc get scaledobject airflow-worker -o jsonpath='{.spec.maxReplicaCount}')
[ "$(kc get scaledobject airflow-worker -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')" = True ] ||
  fail "ScaledObject airflow-worker is not Ready"
end=$((SECONDS + 300))
until [ "$(replicas)" = "$min" ] || [ $SECONDS -ge $end ]; do sleep 5; done
[ "$(replicas)" = "$min" ] || fail "workers did not settle at the minimum ($min) before the burst: $(replicas)"
say "workers at the minimum: $min (max $max)"

was_paused=$(api GET "/api/v2/dags/$DAG" | jq -r .is_paused)
api PATCH "/api/v2/dags/$DAG" '{"is_paused":false}' >/dev/null
run=$(api POST "/api/v2/dags/$DAG/dagRuns" \
  "{\"logical_date\":null,\"conf\":{\"tasks\":$TASKS,\"seconds\":$SECONDS_PER_TASK}}" | jq -r .dag_run_id)
start=$SECONDS
say "triggered $run: $TASKS tasks x ${SECONDS_PER_TASK}s"

peak=$min first_out="" state=""
while :; do
  r=$(replicas); r=${r:-0}
  [ "$r" -gt "$peak" ] && { peak=$r; say "workers: $r available (desired $(desired))"; }
  [ -z "$first_out" ] && [ "$r" -gt "$min" ] && first_out=$((SECONDS - start))
  state=$(api GET "/api/v2/dags/$DAG/dagRuns/$run" | jq -r .state)
  case "$state" in success | failed) break ;; esac
  [ $((SECONDS - start)) -lt 900 ] || fail "run $run still $state after 15 minutes"
  sleep 3
done
took=$((SECONDS - start))
tis=$(api GET "/api/v2/dags/$DAG/dagRuns/$run/taskInstances?task_id=hold_slot&limit=100")
ok=$(jq '[.task_instances[] | select(.state=="success" and .try_number==1)] | length' <<<"$tis")
say "run $run $state in ${took}s; $ok/$TASKS tasks succeeded on try 1; peak $peak workers (first scale-out after ${first_out:-never}s)"
[ "$state" = success ] && [ "$ok" = "$TASKS" ] ||
  fail "not every task succeeded on its first try: $(jq -c '[.task_instances[] | {map_index, state, try_number}]' <<<"$tis")"
[ "$peak" -gt "$min" ] || fail "workers never scaled out above $min"
echo "ok: KEDA scaled the workers $min -> $peak for the burst; no task lost to a scale-in"

end=$((SECONDS + 600))
while [ "$(replicas)" != "$min" ] && [ $SECONDS -lt $end ]; do sleep 5; done
[ "$(replicas)" = "$min" ] || fail "workers still at $(replicas) 10 minutes after the burst"
echo "ok: workers back at $min $((SECONDS - start - took))s after the run finished"

# Scale-in while a task runs (issue #3). The burst above never sees it: the stabilisation window keeps
# every worker until the burst ends. So hold one extra worker by raising the minimum, run one task,
# make its pod the cheapest to delete, and drop the minimum back: the HPA removes exactly that pod.
# A task shorter than the grace period must finish during Celery's warm shutdown; a longer one is
# SIGKILLed, and the scheduler must fail it once its heartbeat is task_instance_heartbeat_timeout old.
grace=$(kc get deploy airflow-worker -o jsonpath='{.spec.template.spec.terminationGracePeriodSeconds}')
set_min() { kc patch scaledobject airflow-worker --type merge -p "{\"spec\":{\"minReplicaCount\":$1}}" >/dev/null 2>&1; }
ti_state() { api GET "/api/v2/dags/$DAG/dagRuns/$1/taskInstances/hold_slot/0" 2>/dev/null || echo '{}'; }

scale_in_during() { # task-seconds expected-state(success|failed)
  local secs=$1 expect=$2 run host pod t0 deleted="" gone="" end st
  set_min $((min + 1))
  end=$((SECONDS + 300))
  until [ "$(replicas)" = $((min + 1)) ] || [ $SECONDS -ge $end ]; do sleep 3; done
  [ "$(replicas)" = $((min + 1)) ] || fail "workers did not scale out to $((min + 1)) for the scale-in drill"
  run=$(api POST "/api/v2/dags/$DAG/dagRuns" \
    "{\"logical_date\":null,\"conf\":{\"tasks\":1,\"seconds\":$secs}}" | jq -r .dag_run_id)
  end=$((SECONDS + 180)) host=""
  until [ -n "$host" ] || [ $SECONDS -ge $end ]; do
    host=$(ti_state "$run" | jq -r 'select(.state=="running") | .hostname // empty')
    sleep 2
  done
  [ -n "$host" ] || fail "the ${secs}s task of $run never started"
  pod=$(worker_pod "$host")
  # ReplicaSets delete the pod with the lowest deletion cost first (default 0).
  kc annotate pod "$pod" controller.kubernetes.io/pod-deletion-cost=-100 --overwrite >/dev/null
  set_min "$min"
  t0=$SECONDS
  say "${secs}s task running on $pod; minimum back to $min"
  while :; do
    st=$(ti_state "$run" | jq -r .state)
    if [ -z "$deleted" ] && [ -n "$(kc get pod "$pod" -o jsonpath='{.metadata.deletionTimestamp}' 2>/dev/null)" ]; then
      deleted=$((SECONDS - t0))
      [ "$st" = running ] || fail "the task was $st before its worker was told to stop"
      say "scale-in picked $pod after ${deleted}s; the task is still running"
    fi
    if [ -z "$gone" ] && ! kc get pod "$pod" >/dev/null 2>&1; then
      gone=$((SECONDS - t0))
      say "$pod gone after ${gone}s"
    fi
    case "$st" in success | failed) break ;; esac
    [ $((SECONDS - t0)) -lt 600 ] || fail "task of $run still $st 10 minutes after the scale-in"
    sleep 3
  done
  [ -n "$deleted" ] || fail "the HPA never removed $pod (is the KEDA metric failing? KA describe hpa)"
  [ "$deleted" -le 60 ] || fail "the HPA took ${deleted}s to scale in (expected one 15 s loop)"
  [ "$st" = "$expect" ] || fail "${secs}s task ended $st, expected $expect"
  say "${secs}s task $st $((SECONDS - t0))s after the scale-in"
}

scale_in_during $((grace - 15)) success
echo "ok: a task shorter than the ${grace}s grace period finished during the warm shutdown"
scale_in_during $((grace * 4)) failed
echo "ok: a task longer than the ${grace}s grace period was killed and failed on its heartbeat timeout"
echo "keda-check passed"
