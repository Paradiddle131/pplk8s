#!/usr/bin/env bash
# Phase 2 exit check (PLAN.md): EL Factory lite answers inside the cluster and stages through the
# `gcs` hostname, and each dbt stage completes as a Kubernetes Job created from `kubectl apply`.
# Expects `make workloads-up` to have run. Re-runnable: the same run_id leaves counts unchanged
# and every dbt Job gets a fresh name.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
ELF_IMAGE="${ELF_IMAGE:?}"
RUN_ID=phase2__check
GCS=http://localhost:4480
k() { kubectl --context kind-pplk8s -n workloads "$@"; }
psql_wh() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d warehouse -Atc "$1"
}
fail() { echo "FAIL: $*" >&2; exit 1; }

k rollout status deployment/el-factory --timeout=120s >/dev/null || fail "el-factory rollout"
ready=$(k get deployment el-factory -o jsonpath='{.status.readyReplicas}')
[ "$ready" = 2 ] || fail "expected 2 ready replicas, got ${ready:-0}"
echo "ok: el-factory Deployment has $ready ready replicas"

# A throwaway pod in the cluster plays the caller (Airflow in Phase 4). It reuses the EL Factory image,
# which ships Python, so no extra image is pulled. It runs the full paginated extract by Service DNS name.
EXTRACT_PY='
import json, os, urllib.request

BASE = "http://el-factory.workloads.svc.cluster.local"
START, END = "2026-10-01T00:00:00Z", "2026-10-03T00:00:00Z"


def call(path, body=None):
    req = urllib.request.Request(BASE + path, method="POST" if body else "GET",
                                 data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


entities = call("/catalog?pipeline=sales")
assert entities, "empty catalog"
for e in entities:
    body = {**e, "run_id": os.environ["RUN_ID"], "interval_start": START, "interval_end": END}
    url, calls, pages = "/extract", 0, 0
    while url:
        answer = call(url, body)
        url, calls, pages = answer["next_url"], calls + 1, pages + answer["pages"]
    print("extracted", e["source"], e["entity"], pages, "pages in", calls, "requests")
'

# The pod spec is given whole via --overrides (kubectl run replaces the image CMD otherwise), with a
# restricted-profile security context so the namespace's Pod Security warning stays quiet.
in_cluster_extract() {
  local pod overrides
  pod="elf-check-$(date +%s)"
  overrides=$(jq -nc --arg name "$pod" --arg image "$ELF_IMAGE" --arg run "$RUN_ID" --arg code "$EXTRACT_PY" '{spec: {
    securityContext: {runAsNonRoot: true, seccompProfile: {type: "RuntimeDefault"}},
    containers: [{name: $name, image: $image, command: ["python", "-c", $code],
      env: [{name: "RUN_ID", value: $run}],
      securityContext: {allowPrivilegeEscalation: false, capabilities: {drop: ["ALL"]}}}]}}')
  k run "$pod" --image="$ELF_IMAGE" --restart=Never --rm -i --quiet --overrides="$overrides"
}
in_cluster_extract || fail "in-cluster extract"
echo "ok: in-cluster extract of pipeline sales finished"

counts() { # objects:customers:orders for this run
  local objects
  objects=$(curl -sf "$GCS/storage/v1/b/staging/o?prefix=synthetic/" |
    jq --arg r "$RUN_ID" '[.items[]? | select(.name | contains("/" + $r + "/"))] | length')
  echo "$objects:$(psql_wh "select count(*) from ds_source.synthetic_customers where _run_id = '$RUN_ID'"):$(psql_wh "select count(*) from ds_source.synthetic_orders where _run_id = '$RUN_ID'")"
}
first=$(counts)
IFS=: read -r objects customers orders <<<"$first"
[ "$objects" -gt 0 ] && [ "$customers" -gt 0 ] && [ "$orders" -gt 0 ] ||
  fail "expected staged objects and rows, got objects=$objects customers=$customers orders=$orders"
echo "ok: staged $objects objects in fake-gcs, loaded $customers customers and $orders orders"

in_cluster_extract >/dev/null || fail "in-cluster re-extract"
second=$(counts)
[ "$first" = "$second" ] || fail "re-run changed counts: $first -> $second"
echo "ok: re-running $RUN_ID left counts unchanged ($second)"

for stage in bronze silver gold exposed; do
  "$REPO/platform/k8s/dbt-job.sh" "$stage" >"/tmp/pplk8s-dbt-job-$stage.log" 2>&1 ||
    { tail -30 "/tmp/pplk8s-dbt-job-$stage.log" >&2; fail "dbt Job for stage $stage"; }
  echo "ok: dbt Job $stage complete"
done

for rel in gold.daily_sales gold.customer_lifetime exposed.sales_by_country_daily; do
  n=$(psql_wh "select count(*) from $rel")
  [ "$n" -gt 0 ] || fail "$rel is empty"
  echo "ok: $rel has $n rows"
done
