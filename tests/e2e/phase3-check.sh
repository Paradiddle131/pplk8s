#!/usr/bin/env bash
# Phase 3 exit check (PLAN.md): the hello DAG runs on a Celery worker pod, and a
# `helm upgrade` followed by `helm rollback` leaves the deployment healthy.
# Expects `make airflow-up` to have run.
set -euo pipefail

source "$(dirname "$0")/lib/airflow-api.sh"
RELEASE=airflow
hm() { helm --kube-context "$CTX" -n "$NS" "$@"; }

# Trigger hello and wait for it to finish; prints the host that ran the task.
run_hello() {
  local run_id state host
  start_port_forward
  refresh_token
  # The dag-processor parses the DAG folder periodically; wait until hello is known.
  for _ in $(seq 60); do api GET /api/v2/dags/hello >/dev/null 2>&1 && break; sleep 2; done
  api GET /api/v2/dags/hello >/dev/null || fail "hello DAG never appeared"
  api PATCH /api/v2/dags/hello '{"is_paused":false}' >/dev/null
  run_id=$(api POST /api/v2/dags/hello/dagRuns '{"logical_date":null}' | jq -r .dag_run_id)
  [ -n "$run_id" ] && [ "$run_id" != null ] || fail "could not trigger hello"
  for _ in $(seq 90); do
    state=$(api GET "/api/v2/dags/hello/dagRuns/$run_id" | jq -r .state)
    case "$state" in success) break ;; failed) fail "hello run $run_id failed" ;; esac
    sleep 2
  done
  [ "$state" = success ] || fail "hello run $run_id still $state after 180 s"
  host=$(api GET "/api/v2/dags/hello/dagRuns/$run_id/taskInstances/say_hello" | jq -r .hostname)
  # The task reports its FQDN (airflow-worker-N.airflow-worker.airflow.svc...).
  [[ "$host" =~ ^airflow-worker-[0-9]+(\.|$) ]] || fail "task ran on '$host', not an airflow-worker pod"
  echo "$host"
}

assert_healthy() {
  local kind name
  for kind in deployment statefulset; do
    for name in $(kc get "$kind" -o name); do
      kc rollout status "$name" --timeout=300s >/dev/null || fail "$name not Ready"
    done
  done
}

# (a) hello on a Celery worker.
host=$(run_hello)
echo "ok: hello succeeded on $host"

# (b) upgrade with a harmless change, preview it with helm diff, then roll back.
before=$(hm history "$RELEASE" -o json | jq 'last.revision')
change=(--reuse-values --version 1.22.0 --set config.celery.worker_concurrency=8)
# Jobs are plain, immutable resources (values.yaml); clear finished ones as deploy.sh does.
kc delete job --ignore-not-found --wait=true "$RELEASE-run-airflow-migrations" "$RELEASE-create-user" >/dev/null
diff_out=$(hm diff upgrade "$RELEASE" apache-airflow/airflow "${change[@]}" --no-color) ||
  fail "helm diff failed"
grep -q 'worker_concurrency' <<<"$diff_out" || fail "helm diff does not show the expected change"
echo "ok: helm diff previews the change ($(grep -c '^[+-] ' <<<"$diff_out") changed lines)"

hm upgrade "$RELEASE" apache-airflow/airflow "${change[@]}" --wait --wait-for-jobs --timeout 10m >/dev/null
after=$(hm history "$RELEASE" -o json | jq 'last.revision')
[ "$after" -gt "$before" ] || fail "upgrade did not create a new revision"
kc get cm airflow-config -o jsonpath='{.data.airflow\.cfg}' | grep -q 'worker_concurrency = 8' ||
  fail "upgrade did not apply the change"
echo "ok: upgraded revision $before -> $after"

hm rollback "$RELEASE" "$before" --wait --wait-for-jobs --timeout 10m >/dev/null
rolled=$(hm history "$RELEASE" -o json | jq 'last.revision')
kc get cm airflow-config -o jsonpath='{.data.airflow\.cfg}' | grep -q 'worker_concurrency = 16' ||
  fail "rollback did not restore the previous config"
echo "ok: rolled back to revision $before as revision $rolled"

assert_healthy
echo "ok: all deployments and statefulsets Ready"
host=$(run_hello)
echo "ok: hello succeeded again after rollback on $host"
echo "phase3-check passed"
