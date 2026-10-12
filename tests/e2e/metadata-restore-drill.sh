#!/usr/bin/env bash
# Phase 6 drill 10 (PLAN.md D28, D32; issue #21): restore the metadata DB to an earlier point while
# the warehouse keeps everything written since, as a Cloud SQL restore or a Composer snapshot load does.
#   1. back up the metadata DB (pg_dump, as Airflow runs), then run past the backup: finance_daily for
#      $DAY waits on sales_elt for $DAY and on a returns file for $DAY through the event path
#   2. restore the backup in place: Airflow, PgBouncer and the workers stopped, database `airflow`
#      dropped and restored, Airflow started
#   3. the three runs are gone from Airflow, the warehouse is unchanged, and
#      AirflowMetadataBehindWarehouse fires once per lost run
#   4. the file event redelivered: the adapter re-creates its run under the same id, which
#      short-circuits on ops.file_loads and loads nothing; that run's alert resolves
#   5. recover (runbook): scripts/metadata-reconcile.sh --replay re-runs the other lost runs under
#      their ids; the warehouse is unchanged, the alert resolves, the canary runs
# Runs on the lab's own metadata DB, so everything Airflow recorded after the backup (only this
# drill's runs) is lost by design. Expects `make airflow-up observability-up workloads-up`; ~15 min.
# The exit trap brings Airflow back if the drill stopped it, restores the DAGs' paused flags and
# KEDA's scaling, and discards the scheduled runs unpausing created.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
source "$(dirname "$0")/lib/airflow-api.sh"
source "$(dirname "$0")/lib/prometheus.sh"
COMPOSE=(docker compose -f "$REPO/platform/compose/compose.yaml")
DAY=2026-09-28 # an interval no other check uses; sales_elt's schedule starts on 2026-10-01
INTERVAL_START="$DAY 00:00:00+00"
INTERVAL_END='2026-09-29 00:00:00+00'
LOGICAL=2026-09-29 # a manual run on this logical date processes [$DAY, +1 day)
BUCKET=landing
OBJECT="returns/$DAY.jsonl"
GCS=http://localhost:4480
PUBSUB=http://localhost:8085/v1/projects/pplk8s
DAGS=(sales_elt returns_file_arrival finance_daily)
ALERT=AirflowMetadataBehindWarehouse
BACKUP="$(mktemp -d)/airflow.dump"
say() { echo "[$(date +%T)] $*"; }

# ---- restorable state -------------------------------------------------------------------------------
declare -A ORIG_PAUSED=() REPLICAS=()
STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
stopped=""
cleanup() {
  local rc=$? dag
  set +e
  [ -z "$stopped" ] || start_airflow
  keda_resume >/dev/null 2>&1
  ensure_port_forward && refresh_token
  for dag in "${!ORIG_PAUSED[@]}"; do
    [ "${ORIG_PAUSED[$dag]}" = true ] || continue
    api PATCH "/api/v2/dags/$dag" '{"is_paused":true}' >/dev/null && echo "re-paused $dag"
    discard_scheduled_runs "$dag" "$STARTED"
  done
  rm -rf "$(dirname "$BACKUP")"
  stop_prometheus
  stop_port_forward
  exit $rc
}
trap cleanup EXIT

# ---- helpers ----------------------------------------------------------------------------------------
psql_wh() { "${COMPOSE[@]}" exec -T warehouse psql -U warehouse -d warehouse -v ON_ERROR_STOP=1 -Atc "$1"; }
meta_psql() { # db sql
  "${COMPOSE[@]}" exec -T metadata-db psql -U airflow -d "$1" -v ON_ERROR_STOP=1 -Atqc "$2"
}
keda_pause() { kc annotate scaledobject airflow-worker --overwrite "autoscaling.keda.sh/paused-replicas=$1" >/dev/null; }
keda_resume() { kc annotate scaledobject airflow-worker autoscaling.keda.sh/paused-replicas- >/dev/null; }
# Nothing may hold a connection during the restore, and PgBouncer must not serve the old database
# to a pod that starts early (upgrade drill, issue #11). KEDA would bring a worker back at once.
stop_airflow() {
  local d
  for d in $(kc get deploy -o name); do REPLICAS[$d]=$(kc get "$d" -o jsonpath='{.spec.replicas}'); done
  stopped=1
  keda_pause 0
  kc scale deploy --all --replicas=0 >/dev/null
  kc delete pod -l component=pgbouncer --grace-period=1 --ignore-not-found --wait=true >/dev/null
  kc wait --for=delete pod -l 'component in (scheduler,api-server,dag-processor,triggerer,worker)' --timeout=300s >/dev/null
}
start_airflow() {
  local d
  for d in "${!REPLICAS[@]}"; do kc scale "$d" --replicas="${REPLICAS[$d]}" >/dev/null; done
  keda_resume
  for d in "${!REPLICAS[@]}"; do kc rollout status "$d" --timeout=300s >/dev/null || fail "$d not ready"; done
  stopped=""
}
run_path() { echo "/api/v2/dags/$1/dagRuns/$(jq -rn --arg r "$2" '$r|@uri')"; }
run_state() { api GET "$(run_path "$1" "$2")" 2>/dev/null | jq -r .state || echo absent; } # dag run
wait_run() { # dag run timeout -> seconds until success
  local start=$SECONDS end=$((SECONDS + $3)) state=""
  while [ $SECONDS -lt $end ]; do
    state=$(run_state "$1" "$2")
    [ "$state" = success ] && { echo $((SECONDS - start)); return 0; }
    [ "$state" = failed ] && fail "$1 run $2 failed"
    sleep 5
  done
  fail "$1 run $2 is '$state' after $3 s"
}
trigger() { # dag run_id -> triggers it for $LOGICAL
  api POST "/api/v2/dags/$1/dagRuns" \
    "{\"dag_run_id\":\"$2\",\"logical_date\":\"${LOGICAL}T00:00:00.$(date +%N | cut -c1-6)Z\"}" >/dev/null ||
    fail "could not trigger $1"
}
upload() { # NDJSON on stdin -> prints the new object generation
  curl -sf -X POST --data-binary @- -H 'Content-Type: application/x-ndjson' \
    "$GCS/upload/storage/v1/b/$BUCKET/o?uploadType=media&name=$(jq -rn --arg o "$OBJECT" '$o|@uri')" |
    jq -r .generation
}
republish() { # generation: the notification fake-gcs sends, as Pub/Sub would redeliver it
  local attrs
  attrs=$(jq -cn --arg b "$BUCKET" --arg o "$OBJECT" --arg g "$1" \
    '{bucketId:$b, objectId:$o, objectGeneration:$g, eventType:"OBJECT_FINALIZE", payloadFormat:"JSON_API_V1"}')
  curl -sf -X POST -H 'Content-Type: application/json' \
    -d "{\"messages\":[{\"attributes\":$attrs,\"data\":\"$(printf '{}' | base64)\"}]}" \
    "$PUBSUB/topics/gcs-object-events:publish" >/dev/null || fail "could not publish to the emulator"
}
event_run() { # generation timeout -> the returns_file_arrival run carrying it, once there is one
  local end=$((SECONDS + $2)) id=""
  while [ $SECONDS -lt $end ]; do
    id=$(api GET "/api/v2/dags/returns_file_arrival/dagRuns?limit=50&order_by=-run_after" |
      jq -r --arg g "$1" '[.dag_runs[] | select(.conf.generation == $g) | .dag_run_id] | first // empty')
    [ -n "$id" ] && { echo "$id"; return 0; }
    sleep 3
  done
  fail "no returns_file_arrival run for generation $1 after $2 s"
}
ti_state() { api GET "$(run_path "$1" "$2")/taskInstances/$3" | jq -r .state; } # dag run task
# Everything the drill's runs wrote, as one comparable line: every gold/exposed table, the drill's
# ds_source rows, its file loads, and its readiness rows. A row-count and content hash per table.
warehouse_sig() {
  local t out=""
  for t in gold.daily_sales gold.customer_lifetime gold.daily_weather silver.returns \
    exposed.sales_by_country_daily exposed.daily_sales_with_weather exposed.net_sales_daily; do
    out+="$t=$(psql_wh "SELECT count(*) || ':' || coalesce(md5(string_agg(x::text, '|' ORDER BY x::text)), '-') FROM $t x") "
  done
  out+="ds_source=$(psql_wh "SELECT (SELECT count(*) FROM ds_source.synthetic_orders WHERE _interval_start = '$INTERVAL_START')
    || '/' || (SELECT count(*) FROM ds_source.partner_returns WHERE _source_uri = 'gs://$BUCKET/$OBJECT')") "
  out+="file_loads=$(psql_wh "SELECT count(*) FROM ops.file_loads WHERE object = '$OBJECT'")"
  echo "$out"
}
readiness() { # -> "product=dag_id/run_id ..." for the drill's interval
  psql_wh "SELECT string_agg(product || '=' || coalesce(dag_id, '-') || '/' || run_id, ' ' ORDER BY product)
           FROM ops.readiness WHERE interval_start = '$INTERVAL_START' AND interval_end = '$INTERVAL_END'"
}
alerting_runs() { # -> the run ids AirflowMetadataBehindWarehouse fires for, sorted
  prom "ALERTS{alertname=\"$ALERT\", alertstate=\"firing\"}" | jq -r '[.[].metric.run_id] | sort | join(" ")'
}
wait_alerting() { # "expected run ids" timeout -> seconds until the alert fires for exactly those
  local start=$SECONDS end=$((SECONDS + $2)) got=""
  while [ $SECONDS -lt $end ]; do
    got=$(alerting_runs)
    [ "$got" = "$1" ] && { echo $((SECONDS - start)); return 0; }
    sleep 5
  done
  fail "$ALERT fires for '$got', expected '$1', after $2 s"
}

# ---- preflight --------------------------------------------------------------------------------------
"${COMPOSE[@]}" exec -T metadata-db true || fail "metadata-db is not running (make services-up)"
start_prometheus
start_port_forward
refresh_token
for dag in "${DAGS[@]}"; do
  wait_dag_ready "$dag"
  ORIG_PAUSED[$dag]=$(api GET "/api/v2/dags/$dag" | jq -r .is_paused)
  api PATCH "/api/v2/dags/$dag" '{"is_paused":false}' >/dev/null
done
[ "$(alert_state "$ALERT")" = inactive ] || fail "$ALERT is already $(alert_state "$ALERT") for: $(alerting_runs)"
# The interval is the drill's own: start it with nothing ready, so finance_daily waits for real.
psql_wh "DELETE FROM ops.readiness WHERE interval_start = '$INTERVAL_START' AND interval_end = '$INTERVAL_END'" >/dev/null
say "preflight: lab healthy, $ALERT inactive, interval [$DAY, $LOGICAL) reset; canary on $(run_hello)"
echo "ok: preflight"

# ---- 1. back up, then run past the backup -----------------------------------------------------------
"${COMPOSE[@]}" exec -T metadata-db pg_dump -U airflow -Fc airflow >"$BACKUP"
BACKED_UP=$(date -u +%FT%TZ)
say "1. backed up the metadata DB ($(du -h "$BACKUP" | cut -f1)) at $BACKED_UP, with Airflow running"
tag=$(date +%s)
FIN_RUN="drill10__finance__$tag"
SALES_RUN="drill10__sales__$tag"
trigger finance_daily "$FIN_RUN"
trigger sales_elt "$SALES_RUN"
GEN=$(printf '{"return_id":"D10-%s","order_id":"O-%s","returned_at":"%sT%02d:00:00+00:00","amount":"%s.00","reason":"drill10"}\n' \
  1 1 "$DAY" 1 3 2 2 "$DAY" 2 5 | upload) || fail "upload failed"
RET_RUN=$(event_run "$GEN" 120)
say "  past the backup: $SALES_RUN, $RET_RUN (generation $GEN), $FIN_RUN waiting on both"
took=$(wait_run sales_elt "$SALES_RUN" 900)
say "  sales_elt succeeded in ${took}s"
wait_run returns_file_arrival "$RET_RUN" 600 >/dev/null
took=$(wait_run finance_daily "$FIN_RUN" 900)
say "  finance_daily succeeded ${took}s after sales_elt"
SIG=$(warehouse_sig)
READY=$(readiness)
say "  readiness: $READY"
for run in "$SALES_RUN" "$RET_RUN" "$FIN_RUN"; do
  grep -q "/$run" <<<"$READY" || fail "no readiness row by $run: $READY"
done
echo "ok: (1) backed up, then three runs past the backup wrote the warehouse"

# ---- 2. restore in place ----------------------------------------------------------------------------
say "2. restoring the backup in place"
stop_airflow
meta_psql postgres "DROP DATABASE airflow WITH (FORCE)" >/dev/null
meta_psql postgres "CREATE DATABASE airflow OWNER airflow" >/dev/null
"${COMPOSE[@]}" exec -T metadata-db pg_restore -U airflow -d airflow --no-owner <"$BACKUP"
RESTORED=$(date -u +%FT%TZ)
start_airflow
start_port_forward
refresh_token
say "  Airflow back on the restored DB; canary on $(run_hello)"
echo "ok: (2) restored the backup of $BACKED_UP in place"

# ---- 3. what the restore did ------------------------------------------------------------------------
for dag_run in "sales_elt $SALES_RUN" "returns_file_arrival $RET_RUN" "finance_daily $FIN_RUN"; do
  # shellcheck disable=SC2086
  [ "$(run_state $dag_run)" = absent ] || fail "$dag_run survived the restore"
done
say "3. the three runs are gone from Airflow; runs created since the restore:"
for dag in "${DAGS[@]}"; do
  api GET "/api/v2/dags/$dag/dagRuns?limit=20&order_by=-run_after" |
    jq -r --arg s "$RESTORED" '.dag_runs[] | select((.queued_at // "") >= $s) | "    \(.dag_id) \(.dag_run_id) \(.run_type) \(.state)"'
done
[ "$(warehouse_sig)" = "$SIG" ] || fail "the warehouse changed across the restore: $(warehouse_sig) vs $SIG"
expected=$(printf '%s\n' "$SALES_RUN" "$RET_RUN" "$FIN_RUN" | sort | paste -sd' ')
took=$(wait_alerting "$expected" 420)
say "  detected: $ALERT firing for the three runs ${took}s after Airflow came back"
say "  metadata-reconcile.sh lists:"
"$REPO/scripts/metadata-reconcile.sh" | tee /dev/stderr | grep -c . | grep -qx 3 ||
  fail "metadata-reconcile.sh should list exactly the three lost runs"
echo "ok: (3) the restore lost three runs, the warehouse kept their rows, and $ALERT fired for each"

# ---- 4. a redelivered event ------------------------------------------------------------------------
republish "$GEN"
again=$(event_run "$GEN" 120)
[ "$again" = "$RET_RUN" ] || fail "the redelivery created $again, not $RET_RUN"
wait_run returns_file_arrival "$RET_RUN" 300 >/dev/null
[ "$(ti_state returns_file_arrival "$RET_RUN" load)" = skipped ] || fail "the redelivered run loaded the file again"
[ "$(warehouse_sig)" = "$SIG" ] || fail "the redelivered run changed the warehouse"
took=$(wait_alerting "$(printf '%s\n' "$SALES_RUN" "$FIN_RUN" | sort | paste -sd' ')" 300)
say "4. redelivered generation $GEN: run $RET_RUN re-created, load skipped on ops.file_loads; its alert resolved after ${took}s"
echo "ok: (4) the event ledger kept the redelivery from loading twice"

# ---- 5. recover --------------------------------------------------------------------------------------
say "5. scripts/metadata-reconcile.sh --replay"
"$REPO/scripts/metadata-reconcile.sh" --replay | sed 's/^/    /'
took=$(wait_run sales_elt "$SALES_RUN" 900)
say "  $SALES_RUN replayed in ${took}s"
wait_run finance_daily "$FIN_RUN" 600 >/dev/null
[ "$(warehouse_sig)" = "$SIG" ] || fail "the replays changed the warehouse: $(warehouse_sig) vs $SIG"
[ "$(readiness)" = "$READY" ] || fail "the replays changed ops.readiness: $(readiness) vs $READY"
took=$(wait_alert "$ALERT" inactive 300)
say "  warehouse and readiness unchanged; $ALERT resolved after ${took}s; canary on $(run_hello)"
"$REPO/scripts/metadata-reconcile.sh" | grep -q 'every run' || fail "reconcile still lists lost runs"
echo "ok: (5) replayed under their own ids: Airflow's history matches the warehouse again"
echo "metadata-restore-drill passed"
