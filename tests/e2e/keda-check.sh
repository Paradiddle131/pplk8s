#!/usr/bin/env bash
# KEDA check (PLAN.md D24): a burst of ops_load_test tasks scales the Celery workers from the
# minimum out to more than one replica, every task succeeds on its first try (no task killed by a
# scale-in), and the workers scale back to the minimum after the cooldown. Expects `make airflow-up`
# (KEDA on). Re-runnable: each run is new, and the DAG's paused flag is restored on exit.
set -euo pipefail

source "$(dirname "$0")/lib/airflow-api.sh"
DAG=ops_load_test
TASKS=${TASKS:-16}
SECONDS_PER_TASK=${SECONDS_PER_TASK:-45}
say() { echo "[$(date +%T)] $*"; }
replicas() { kc get deploy airflow-worker -o jsonpath='{.status.availableReplicas}'; }
desired() { kc get hpa keda-hpa-airflow-worker -o jsonpath='{.status.desiredReplicas}'; }

was_paused=""
cleanup() {
  local rc=$?
  set +e
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
echo "keda-check passed"
