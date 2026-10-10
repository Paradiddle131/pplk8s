#!/usr/bin/env bash
# KubernetesExecutor experiment (PLAN.md D25), run with the multi-executor overlay applied:
#   make airflow-up AIRFLOW_OVERLAYS=values-multi-executor.yaml
# (a) the same task on Celery and in its own pod: both succeed; prints queued->running latency and
# where each ran; (b) the pod task's log is still served after its pod is gone (remote logs, D22);
# (c) a task that exceeds its own small pod limit fails alone while the Celery workers carry on.
# Numbers go to docs/executors.md. Restores the DAG's paused flag on exit.
set -euo pipefail

source "$(dirname "$0")/lib/airflow-api.sh"
DAG=ops_executor_experiment
say() { echo "[$(date +%T)] $*"; }
was_paused=""
cleanup() {
  local rc=$?
  set +e
  [ "$was_paused" = true ] && api PATCH "/api/v2/dags/$DAG" '{"is_paused":true}' >/dev/null
  # KubernetesExecutor keeps failed pods (the OOM probe's) for inspection; this run is done with them.
  kc delete pod -l "kubernetes_executor=True,dag_id=$DAG" --ignore-not-found >/dev/null
  stop_port_forward
  exit $rc
}
trap cleanup EXIT

start_port_forward
refresh_token
kc get cm airflow-config -o jsonpath='{.data.airflow\.cfg}' | grep -q '^executor = .*KubernetesExecutor' ||
  fail "KubernetesExecutor is not configured; deploy with AIRFLOW_OVERLAYS=values-multi-executor.yaml"
wait_dag_ready "$DAG" 180
was_paused=$(api GET "/api/v2/dags/$DAG" | jq -r .is_paused)
api PATCH "/api/v2/dags/$DAG" '{"is_paused":false}' >/dev/null

run_dag() { # exceed_mb -> run id, after the run finished
  local run state
  run=$(api POST "/api/v2/dags/$DAG/dagRuns" "{\"logical_date\":null,\"conf\":{\"exceed_mb\":$1}}" |
    jq -r .dag_run_id)
  for _ in $(seq 120); do
    state=$(api GET "/api/v2/dags/$DAG/dagRuns/$run" | jq -r .state)
    case "$state" in success | failed) echo "$run"; return 0 ;; esac
    sleep 3
  done
  fail "run $run still $state after 6 minutes"
}
ti() { api GET "/api/v2/dags/$DAG/dagRuns/$1/taskInstances/$2"; }
latency() { # ti json -> seconds from queued to start
  jq -r '((.start_date | sub("\\.[0-9]+";"") | fromdateiso8601) - (.queued_when | sub("\\.[0-9]+";"") | fromdateiso8601))' <<<"$1"
}

# (a) same task, two executors
workers_before=$(kc get pods -l component=worker -o jsonpath='{range .items[*]}{.status.containerStatuses[0].restartCount}{" "}{end}')
run=$(run_dag 0)
for t in on_celery on_kubernetes exceed_memory; do
  j=$(ti "$run" "$t")
  [ "$(jq -r .state <<<"$j")" = success ] || fail "$t did not succeed in $run: $(jq -c '{state, executor}' <<<"$j")"
  say "$t: executor=$(jq -r '.executor // "default (Celery)"' <<<"$j") queued->running=$(latency "$j")s duration=$(jq -r .duration <<<"$j")s host=$(jq -r .hostname <<<"$j")"
done
echo "ok: (a) the task ran on a Celery worker and in a KubernetesExecutor pod"

# (b) the pod is deleted when its task ends; the log must come from gs://airflow-logs
host=$(ti "$run" on_kubernetes | jq -r .hostname)
end=$((SECONDS + 120))
while kc get pods -o wide --no-headers 2>/dev/null | grep -q " $host "; do
  [ $SECONDS -lt $end ] || fail "pod with IP $host still exists"
  sleep 2
done
enc=$(jq -rn --arg r "$run" '$r|@uri')
logs=$(api GET "/api/v2/dags/$DAG/dagRuns/$enc/taskInstances/on_kubernetes/logs/1" | jq -r '[.content[]? | .event // empty] | join("\n")')
grep -q 'gs://airflow-logs' <<<"$logs" || fail "on_kubernetes log not read from gs://airflow-logs after its pod was deleted"
echo "ok: (b) on_kubernetes's pod is gone and its log is served from gs://airflow-logs"

# (c) memory isolation: 600 MiB in a pod limited to 384Mi
run=$(run_dag 600)
oom=$(ti "$run" exceed_memory)
[ "$(jq -r .state <<<"$oom")" = failed ] || fail "exceed_memory was $(jq -r .state <<<"$oom"), expected failed"
[ "$(ti "$run" on_celery | jq -r .state)" = success ] || fail "on_celery failed next to the OOM probe"
[ "$(ti "$run" on_kubernetes | jq -r .state)" = success ] || fail "on_kubernetes failed next to the OOM probe"
workers_after=$(kc get pods -l component=worker -o jsonpath='{range .items[*]}{.status.containerStatuses[0].restartCount}{" "}{end}')
reason=$(kc get events --field-selector reason=OOMKilling -o jsonpath='{.items[-1:].message}' 2>/dev/null || true)
say "exceed_memory failed in its own pod; Celery worker restarts before/after: [$workers_before] [$workers_after]; ${reason:-no OOMKilling event recorded (kind reports it on the node)}"
echo "ok: (c) the over-limit task failed alone; the other tasks of the run succeeded"
echo "executor-experiment passed"
