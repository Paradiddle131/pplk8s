#!/usr/bin/env bash
# Phase 3 exit check (PLAN.md): the hello DAG runs on a Celery worker pod, and a
# `helm upgrade` followed by `helm rollback` leaves the deployment healthy.
# Expects `make airflow-up` to have run.
set -euo pipefail

source "$(dirname "$0")/lib/airflow-api.sh"
RELEASE=airflow
hm() { helm --kube-context "$CTX" -n "$NS" "$@"; }

# (a) hello on a Celery worker.
host=$(run_hello)
echo "ok: hello succeeded on $host"

# (b) upgrade with a harmless change, preview it with helm diff, then roll back.
before=$(hm history "$RELEASE" -o json | jq 'last.revision')
concurrency() { kc get cm airflow-config -o jsonpath='{.data.airflow\.cfg}' | sed -n 's/^worker_concurrency = //p'; }
orig=$(concurrency)
[ -n "$orig" ] || fail "worker_concurrency not found in airflow.cfg"
new=$((orig + 1))
change=(--reuse-values --version 1.22.0 --set "config.celery.worker_concurrency=$new")
# Jobs are plain, immutable resources (values.yaml); clear finished ones as deploy.sh does.
kc delete job --ignore-not-found --wait=true "$RELEASE-run-airflow-migrations" "$RELEASE-create-user" >/dev/null
diff_out=$(hm diff upgrade "$RELEASE" apache-airflow/airflow "${change[@]}" --no-color) ||
  fail "helm diff failed"
grep -q 'worker_concurrency' <<<"$diff_out" || fail "helm diff does not show the expected change"
echo "ok: helm diff previews the change ($(grep -c '^[+-] ' <<<"$diff_out") changed lines)"

hm upgrade "$RELEASE" apache-airflow/airflow "${change[@]}" --wait --wait-for-jobs --timeout 10m >/dev/null
after=$(hm history "$RELEASE" -o json | jq 'last.revision')
[ "$after" -gt "$before" ] || fail "upgrade did not create a new revision"
[ "$(concurrency)" = "$new" ] || fail "upgrade did not apply the change"
echo "ok: upgraded revision $before -> $after"

hm rollback "$RELEASE" "$before" --wait --wait-for-jobs --timeout 10m >/dev/null
rolled=$(hm history "$RELEASE" -o json | jq 'last.revision')
[ "$(concurrency)" = "$orig" ] || fail "rollback did not restore the previous config"
echo "ok: rolled back to revision $before as revision $rolled"

assert_healthy
echo "ok: all deployments and statefulsets Ready"
host=$(run_hello)
echo "ok: hello succeeded again after rollback on $host"
echo "phase3-check passed"
