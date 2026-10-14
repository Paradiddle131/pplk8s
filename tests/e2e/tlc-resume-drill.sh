#!/usr/bin/env bash
# Mid-file resume drill (PLAN.md D34, issue #91; docs/runbook.md Phase 8 drill 2): lose the EL Factory
# pod serving a tlc_monthly extract in the middle of a file, and prove the task's retry resumes after
# the last loaded chunk.
#
#   1. Forget the newest loaded yellow month's chunk ledger (ops.file_chunks, ops.file_versions for
#      the file's current etag), so re-running the month reloads the real file chunk by chunk; the
#      landed rows stay and each chunk replaces its own (D34).
#   2. Clear that month's tlc_monthly run. Once KILL_AFTER chunks are recorded, force-delete the
#      EL Factory pod holding the extract's connection (no grace: a node loss, not a rollout).
#   3. Detect: the extract attempt fails into its retry and AirflowTaskFailures fires.
#   4. Recover: nothing to do; the retry resumes at chunk KILL_AFTER on the surviving pod. Asserts
#      the chunks recorded before the kill were not loaded again, landing rows = ledger rows = the
#      Parquet footer's row count, one completed version, and the month's layers unchanged.
#
# Expects `make airflow-up workloads-up observability-up` and a month phase8-check already loaded.
# On exit the DAG's paused flag is restored.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/airflow-api.sh
source "$(dirname "$0")/lib/airflow-api.sh"
# shellcheck source=lib/prometheus.sh
source "$(dirname "$0")/lib/prometheus.sh"
DAG=tlc_monthly
ENTITY=yellow     # 4 chunks of ~18 MB a month: room to kill between two of them
KILL_AFTER=${KILL_AFTER:-2}
WL=workloads
RUN_TIMEOUT=${RUN_TIMEOUT:-1800}
ALERT_TIMEOUT=${ALERT_TIMEOUT:-300}

say() { echo "[$(date +%T)] $*"; }
psql_wh() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d warehouse -v ON_ERROR_STOP=1 -Atc "$1"
}
elf_pods() { # the EL Factory pods that are not terminating
  kubectl -n "$WL" get pods -l app.kubernetes.io/name=el-factory -o json |
    jq -r '.items[] | select(.metadata.deletionTimestamp == null) | .metadata.name'
}
CLIENTS_PY='
import socket, struct, sys
host = sys.argv[1]
n = 0
for line in open("/proc/net/tcp").readlines()[1:]:
    local, remote, state = line.split()[1:4]
    ip = socket.inet_ntoa(struct.pack("<I", int(remote.split(":")[0], 16)))
    if local.endswith(":1F90") and state == "01" and ip not in (host, "127.0.0.1"):
        n += 1
print(n)'
clients() { # pod -> established connections to :8080 from anything but its node (the kubelet's probes)
  local host
  host=$(kubectl -n "$WL" get pod "$1" -o jsonpath='{.status.hostIP}')
  kubectl -n "$WL" exec "$1" -c el-factory -- python -c "$CLIENTS_PY" "$host"
}

ORIG_PAUSED=""
cleanup() {
  local rc=$?
  set +e
  [ "$ORIG_PAUSED" = true ] && api PATCH "/api/v2/dags/$DAG" '{"is_paused":true}' >/dev/null && echo "re-paused $DAG"
  stop_prometheus
  stop_port_forward
  exit $rc
}
trap cleanup EXIT

run_of() { # YYYY-MM -> the run id whose logical date starts that month
  api GET "/api/v2/dags/$DAG/dagRuns?logical_date_gte=$1-01T00:00:00Z&logical_date_lte=$1-01T00:00:00Z&limit=1" |
    jq -r '.dag_runs[0].dag_run_id // empty'
}
run_path() { echo "/api/v2/dags/$DAG/dagRuns/$(jq -rn --arg r "$1" '$r|@uri')"; }
extract_tis() { # run -> "map-index try state" per extract task instance
  api GET "$(run_path "$1")/taskInstances?task_id=extract&limit=50" |
    jq -r '.task_instances[] | select(.task_id == "extract") | "\(.rendered_map_index // .map_index) \(.try_number) \(.state)"'
}

# ---- setup --------------------------------------------------------------------------------------------
start_port_forward
refresh_token
start_prometheus
wait_dag_ready "$DAG"

# The newest month with a completed yellow version and a successful run.
read -r URI ETAG <<<"$(psql_wh "SELECT source_uri, etag FROM ops.file_versions
  WHERE source_uri LIKE '%/${ENTITY}_tripdata_%' ORDER BY source_uri DESC, completed_at DESC LIMIT 1" | tr '|' ' ')"
[ -n "$URI" ] || fail "no completed $ENTITY file version; run \`make phase8-check\` first"
MONTH=$(sed -E 's/.*_([0-9]{4}-[0-9]{2})\.parquet$/\1/' <<<"$URI")
RUN=$(run_of "$MONTH")
[ -n "$RUN" ] || fail "$MONTH has no $DAG run to clear"
[ "$(api GET "$(run_path "$RUN")" | jq -r .state)" = success ] || fail "$MONTH's run $RUN is not in success"
read -r CHUNKS LEDGER_ROWS <<<"$(psql_wh "SELECT count(*), sum(rows) FROM ops.file_chunks WHERE source_uri = '$URI' AND etag = '$ETAG'" | tr '|' ' ')"
[ "$CHUNKS" -gt "$KILL_AFTER" ] || fail "$URI has $CHUNKS chunks; the drill needs more than KILL_AFTER=$KILL_AFTER"
POD0=$(elf_pods | head -1)
FOOTER_ROWS=$(kubectl -n "$WL" exec "$POD0" -c el-factory -- python -c '
import sys, pyarrow.parquet as pq
from el_factory.remote_file import RangeReader, head
print(pq.ParquetFile(RangeReader(head(sys.argv[1]))).metadata.num_rows)' "$URI")
[ "$FOOTER_ROWS" = "$LEDGER_ROWS" ] || fail "the ledger holds $LEDGER_ROWS rows, the footer of $URI says $FOOTER_ROWS"
layers() { # the month's landed rows of this version, silver and quarantine rows of the entity
  psql_wh "SELECT (SELECT count(*) FROM ds_source.tlc_$ENTITY WHERE _source_uri = '$URI' AND _etag = '$ETAG')
    || ' ' || (SELECT count(*) FROM silver.tlc_trips WHERE data_month = '$MONTH' AND trip_type = '$ENTITY')
    || ' ' || (SELECT count(*) FROM silver.tlc_trips_quarantine WHERE data_month = '$MONTH')"
}
BEFORE=$(layers)
say "$ENTITY $MONTH: run $RUN, $CHUNKS chunks, $FOOTER_ROWS rows, etag $ETAG; landing silver quarantine: $BEFORE"
[ "$(alert_state AirflowTaskFailures)" = inactive ] ||
  fail "AirflowTaskFailures is already $(alert_state AirflowTaskFailures); wait until it clears so the drill's failure is the one it sees"

ORIG_PAUSED=$(api GET "/api/v2/dags/$DAG" | jq -r .is_paused)
api PATCH "/api/v2/dags/$DAG" '{"is_paused":false}' >/dev/null

# ---- 1-2. reload the month and lose the pod mid-file ----------------------------------------------------
psql_wh "BEGIN;
  DELETE FROM ops.file_chunks WHERE source_uri = '$URI' AND etag = '$ETAG';
  DELETE FROM ops.file_versions WHERE source_uri = '$URI' AND etag = '$ETAG';
  COMMIT;" >/dev/null
say "forgot the chunk ledger of $URI; clearing $RUN"
api POST "$(run_path "$RUN")/clear" '{"dry_run":false}' >/dev/null || fail "could not clear $RUN"

recorded() { psql_wh "SELECT count(*) FROM ops.file_chunks WHERE source_uri = '$URI' AND etag = '$ETAG'"; }
end=$((SECONDS + RUN_TIMEOUT))
until [ "$(recorded)" -ge "$KILL_AFTER" ]; do
  [ $SECONDS -lt "$end" ] || fail "fewer than $KILL_AFTER chunks recorded after ${RUN_TIMEOUT}s: $(extract_tis "$RUN" | xargs)"
  sleep 1
done
KILL_TS=$(psql_wh "SELECT now()")
victims=()
for pod in $(elf_pods); do [ "$(clients "$pod")" -gt 0 ] && victims+=("$pod"); done
[ ${#victims[@]} -gt 0 ] || fail "no EL Factory pod holds a client connection after chunk $KILL_AFTER"
kubectl -n "$WL" delete pod "${victims[@]}" --grace-period=0 --force >/dev/null 2>&1
AT_KILL=$(psql_wh "SELECT string_agg(chunk || '@' || loaded_at, ',' ORDER BY chunk) FROM ops.file_chunks
  WHERE source_uri = '$URI' AND etag = '$ETAG' AND loaded_at < '$KILL_TS'")
say "$(recorded) of $CHUNKS chunks recorded; force-deleted ${victims[*]} (serving the extract)"

# ---- 3. detect ------------------------------------------------------------------------------------------
took=$(wait_alert AirflowTaskFailures firing "$ALERT_TIMEOUT")
say "AirflowTaskFailures fired ${took}s after the kill"

# ---- 4. recover: the retry resumes ------------------------------------------------------------------------
end=$((SECONDS + RUN_TIMEOUT))
while :; do
  ensure_port_forward
  refresh_token
  state=$(api GET "$(run_path "$RUN")" | jq -r .state)
  [ "$state" = success ] && break
  [ "$state" = failed ] && fail "$RUN failed: $(extract_tis "$RUN" | xargs)"
  [ $SECONDS -lt "$end" ] || fail "$RUN is still $state after ${RUN_TIMEOUT}s"
  sleep 10
done
tis=$(extract_tis "$RUN")
say "run $RUN succeeded; extract [map-index try state]: $(xargs <<<"$tis")"
awk '$2 >= 2 && $3 == "success" { found = 1 } END { exit !found }' <<<"$tis" ||
  fail "no extract succeeded on a retry; the kill did not fail an attempt"

read -r chunks ledger_rows <<<"$(psql_wh "SELECT count(*), sum(rows) FROM ops.file_chunks WHERE source_uri = '$URI' AND etag = '$ETAG'" | tr '|' ' ')"
[ "$chunks" = "$CHUNKS" ] || fail "$chunks of $CHUNKS chunks recorded after the retry"
kept=$(psql_wh "SELECT string_agg(chunk || '@' || loaded_at, ',' ORDER BY chunk) FROM ops.file_chunks
  WHERE source_uri = '$URI' AND etag = '$ETAG' AND loaded_at < '$KILL_TS'")
[ "$kept" = "$AT_KILL" ] || fail "chunks recorded before the kill were loaded again: [$AT_KILL] -> [$kept]"
landed=$(psql_wh "SELECT count(*) FROM ds_source.tlc_$ENTITY WHERE _source_uri = '$URI' AND _etag = '$ETAG'")
[ "$landed" = "$ledger_rows" ] && [ "$landed" = "$FOOTER_ROWS" ] ||
  fail "landing holds $landed rows, the ledger $ledger_rows, the footer $FOOTER_ROWS"
versions=$(psql_wh "SELECT count(*) FROM ops.file_versions WHERE source_uri = '$URI'")
[ "$versions" = 1 ] || fail "$URI has $versions completed versions"
after=$(layers)
[ "$after" = "$BEFORE" ] || fail "$MONTH's layers changed from [$BEFORE] to [$after]"
say "PASS: the retry resumed after chunks [$AT_KILL]; $landed rows = ledger = footer, one version, layers unchanged [$after]"
