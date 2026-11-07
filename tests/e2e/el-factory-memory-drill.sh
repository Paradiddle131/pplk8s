#!/usr/bin/env bash
# EL Factory memory drill (PLAN.md D35, issue #90; docs/runbook.md Phase 8 drill 1): load real FHVHV
# row groups through one in-cluster EL Factory pod, several months at once.
# Each gunicorn process holds at most one chunk (one Parquet row group) in flight (tlc/chunks.py
# CHUNK_SLOT), so a few chunks per month show the peak: a whole FHVHV month (~20 M rows) would not
# raise it, and would not fit the warehouse's 15 GB budget either.
#
#   tests/e2e/el-factory-memory-drill.sh                     measure: report the pod's cgroup
#       memory.peak and every process's VmHWM; fail if the pod restarted or the peak is not below
#       HEADROOM_PCT of the limit.
#   TIGHT_LIMIT=448Mi tests/e2e/el-factory-memory-drill.sh   detect: shrink EL Factory's memory
#       limit, load until WorkloadContainerMemoryNearLimit and WorkloadContainerOOMKilled both fire
#       in Prometheus, then roll the Deployment back to the manifest's limit.
#
# Afterwards drops the FHVHV landing table and its chunk ledgers, so the warehouse gives the space
# back to the disk. Downloads ~30 MB per chunk. Expects `make workloads-up observability-up`.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
NS=workloads
# FHVHV months with 19-22 row groups of ~1 M rows; 2026-05 is the largest file (538 MB).
read -r -a MONTHS <<<"${MONTHS:-2026-05 2026-08 2025-02}"
CHUNKS=${CHUNKS:-2}              # chunks to load per month
HEADROOM_PCT=${HEADROOM_PCT:-85} # measure: the peak must stay below this share of the limit
TIGHT_LIMIT=${TIGHT_LIMIT:-}     # detect: the memory limit to shrink EL Factory to
ALERT_TIMEOUT=${ALERT_TIMEOUT:-600}
LOCAL_PORT=${LOCAL_PORT:-18090}
PROM_PORT=${PROM_PORT:-19090}
RUN_ID_PREFIX=memdrill

say() { echo "[$(date +%T)] $*"; }
psql_wh() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d warehouse -v ON_ERROR_STOP=1 -Atc "$1"
}
in_pod() { kubectl exec -n "$NS" "$POD" -c el-factory -- sh -c "$1"; }
restarts() { kubectl get pod -n "$NS" "$POD" -o jsonpath='{.status.containerStatuses[0].restartCount}'; }
firing() { # the alert is firing for el-factory in Prometheus
  curl -s --max-time 5 "localhost:$PROM_PORT/api/v1/query" --data-urlencode \
    "query=ALERTS{alertname=\"$1\", alertstate=\"firing\", namespace=\"$NS\", container=\"el-factory\"}" |
    jq -e '.data.result | length > 0' >/dev/null
}

PIDS_TO_KILL=()
SAVED_RESOURCES="" # detect mode: the container's resources before shrinking, restored on exit
WORK=$(mktemp -d)
cleanup() {
  local rc=$?
  set +e
  for pid in "${PIDS_TO_KILL[@]}"; do kill "$pid" 2>/dev/null; done
  jobs -p | xargs -r kill 2>/dev/null
  if [ -n "$SAVED_RESOURCES" ]; then
    say "restoring el-factory's resources: $SAVED_RESOURCES"
    kubectl patch -n "$NS" deployment/el-factory --type=json -p \
      "[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/resources\",\"value\":$SAVED_RESOURCES}]" >/dev/null
    kubectl rollout status -n "$NS" deployment/el-factory --timeout=180s >/dev/null
  fi
  say "dropping the FHVHV landing table and its chunk ledgers"
  psql_wh "DROP TABLE IF EXISTS ds_source.tlc_fhvhv;
           DELETE FROM ops.file_chunks WHERE source_uri LIKE '%/fhvhv_tripdata_%';
           DELETE FROM ops.file_versions WHERE source_uri LIKE '%/fhvhv_tripdata_%';" >/dev/null
  rm -rf "$WORK"
  exit $rc
}
trap cleanup EXIT

if [ -n "$TIGHT_LIMIT" ]; then
  say "shrinking el-factory's memory limit to $TIGHT_LIMIT"
  SAVED_RESOURCES=$(kubectl get -n "$NS" deployment/el-factory -o jsonpath='{.spec.template.spec.containers[0].resources}')
  kubectl set resources -n "$NS" deployment/el-factory -c el-factory \
    --limits="memory=$TIGHT_LIMIT" --requests="memory=$TIGHT_LIMIT" >/dev/null
  kubectl rollout status -n "$NS" deployment/el-factory --timeout=180s >/dev/null
  kubectl -n monitoring port-forward svc/kps-prometheus "$PROM_PORT:9090" >/dev/null 2>&1 &
  PIDS_TO_KILL+=($!)
fi

# A ready pod that is not terminating: right after a rollout, the old ReplicaSet's pods still
# report phase Running.
POD=$(kubectl get pods -n "$NS" -l app.kubernetes.io/name=el-factory -o json | jq -r '
  [.items[] | select(.metadata.deletionTimestamp == null)
            | select(any(.status.conditions[]?; .type == "Ready" and .status == "True"))][0].metadata.name')
[ "$POD" != null ] || { echo "no ready el-factory pod" >&2; exit 1; }
LIMIT=$(in_pod 'cat /sys/fs/cgroup/memory.max')
RESTARTS_BEFORE=$(restarts)
say "pod $POD, limit $((LIMIT / 1048576)) MiB, idle $(($(in_pod 'cat /sys/fs/cgroup/memory.current') / 1048576)) MiB"

# A port-forward to the one pod; restarted when the container restarts under it (detect mode).
PF_PID=""
forward() {
  [ -n "$PF_PID" ] && kill "$PF_PID" 2>/dev/null
  kubectl port-forward -n "$NS" "pod/$POD" "$LOCAL_PORT:8080" >/dev/null 2>&1 &
  PF_PID=$!
  PIDS_TO_KILL+=("$PF_PID")
  for _ in $(seq 60); do curl -sf --max-time 2 "localhost:$LOCAL_PORT/healthz" >/dev/null && return 0; sleep 1; done
  return 1
}
forward

# One month: POST /extract until CHUNKS chunks are loaded or the file is done. Each request is
# time-boxed (MAX_RUN_TIME) and loads at least one chunk.
load_month() {
  local month=$1 next end resp pages loaded=0
  end=$(date -u -d "$month-01 +1 month" +%Y-%m-01T00:00:00Z)
  local body="{\"source\":\"tlc\",\"entity\":\"fhvhv\",\"run_id\":\"${RUN_ID_PREFIX}__$month\",
    \"interval_start\":\"$month-01T00:00:00Z\",\"interval_end\":\"$end\"}"
  next=/extract
  while [ "$loaded" -lt "$CHUNKS" ]; do
    resp=$(curl -sS --max-time 600 -H 'Content-Type: application/json' -d "$body" "localhost:$LOCAL_PORT$next" 2>&1)
    pages=$(jq -er .pages <<<"$resp") || { say "$month: $resp"; return 1; }
    loaded=$((loaded + pages))
    say "$month: +$pages chunk(s), $loaded of $(jq -r .chunks <<<"$resp") loaded"
    next=$(jq -r '.next_url // empty' <<<"$resp")
    [ -n "$next" ] || break
  done
}
load_all() {
  local pids=() failed=0
  for month in "${MONTHS[@]}"; do
    load_month "$month" &
    pids+=($!)
  done
  for pid in "${pids[@]}"; do wait "$pid" || failed=1; done
  return "$failed"
}

if [ -n "$TIGHT_LIMIT" ]; then
  # Load until both alerts fire; a load that the OOMKill cut short is expected.
  deadline=$((SECONDS + ALERT_TIMEOUT))
  near="" oom=""
  while [ "$SECONDS" -lt "$deadline" ] && { [ -z "$near" ] || [ -z "$oom" ]; }; do
    load_all || say "a load failed (expected once the container is OOMKilled)"
    [ "$(restarts)" = "$RESTARTS_BEFORE" ] || forward || true
    for _ in $(seq 12); do
      [ -z "$near" ] && firing WorkloadContainerMemoryNearLimit && near=$SECONDS && say "WorkloadContainerMemoryNearLimit is firing"
      [ -z "$oom" ] && firing WorkloadContainerOOMKilled && oom=$SECONDS && say "WorkloadContainerOOMKilled is firing"
      [ -n "$near" ] && [ -n "$oom" ] && break
      sleep 5
    done
  done
  say "restarts $RESTARTS_BEFORE -> $(restarts); last termination: $(kubectl get pod -n "$NS" "$POD" \
    -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}')"
  [ -n "$near" ] || { echo "FAIL: WorkloadContainerMemoryNearLimit never fired" >&2; exit 1; }
  [ -n "$oom" ] || { echo "FAIL: WorkloadContainerOOMKilled never fired" >&2; exit 1; }
  say "PASS: both alerts fired at a $TIGHT_LIMIT limit"
  exit 0
fi

# Sample the working set (usage minus inactive file cache, as the kubelet counts it) every 2 s.
(
  while :; do
    # shellcheck disable=SC2016 # expanded by the pod's shell
    in_pod 'echo $(cat /sys/fs/cgroup/memory.current) $(grep "^inactive_file " /sys/fs/cgroup/memory.stat | cut -d" " -f2)' \
      2>/dev/null | awk '{print $1 - $2}' >>"$WORK/samples"
    sleep 2
  done
) &
SAMPLER=$!
failed=0
load_all || failed=1
kill "$SAMPLER" 2>/dev/null || true

PEAK=$(in_pod 'cat /sys/fs/cgroup/memory.peak')
WS_PEAK=$(sort -n "$WORK/samples" | tail -1)
say "per-process peak RSS (VmHWM):"
# shellcheck disable=SC2016 # expanded by the pod's shell
in_pod 'for s in /proc/[0-9]*/status; do awk "/^(Pid|VmHWM):/ {printf \"%s %s \", \$1, \$2} END {print \"\"}" $s; done'
say "cgroup memory.peak $((PEAK / 1048576)) MiB, sampled working-set peak $((${WS_PEAK:-0} / 1048576)) MiB, limit $((LIMIT / 1048576)) MiB"

[ "$failed" -eq 0 ] || { echo "FAIL: a month's extract failed" >&2; exit 1; }
[ "$(restarts)" = "$RESTARTS_BEFORE" ] || { echo "FAIL: $POD restarted" >&2; exit 1; }
[ "$PEAK" -lt $((LIMIT * HEADROOM_PCT / 100)) ] || { echo "FAIL: peak above ${HEADROOM_PCT}% of the limit" >&2; exit 1; }
say "PASS: peak $((PEAK * 100 / LIMIT))% of the limit"
