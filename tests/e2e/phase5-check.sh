#!/usr/bin/env bash
# Phase 5 exit check (PLAN.md): dropping one file triggers exactly one scoped run; re-delivering the
# same event does not reprocess the same generation. Also checks the consumer DAG's deferrable wait
# on ops.readiness (D19). Expects `make airflow-up workloads-up` to have run.
# Re-runnable: every upload is a new object generation, the consumer's interval is reset first, and
# on exit the DAGs' paused flags are restored and the scheduled runs their unpausing created discarded.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/airflow-api.sh
source "$(dirname "$0")/lib/airflow-api.sh"
PRODUCER=returns_file_arrival
CONSUMER=finance_daily
BUCKET=landing
DAY=2026-10-02 # the file's day (gold.daily_sales has it); the consumer's run on the next day processes it
OBJECT="returns/$DAY.jsonl"
INTERVAL_START="$DAY 00:00:00+00"
INTERVAL_END='2026-10-03 00:00:00+00'
CONSUMER_LOGICAL=2026-10-03
GCS=http://localhost:4480
PUBSUB=http://localhost:8085/v1/projects/pplk8s
wk() { kubectl --context "$CTX" -n workloads "$@"; }
psql_wh() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d warehouse -Atc "$1"
}
say() { echo "[$(date +%T)] $*"; }

# ---- restorable state: paused flags and the scheduled runs unpausing creates ---------------------------
declare -A ORIG_PAUSED=()
STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cleanup() {
  local rc=$? dag
  set +e
  for dag in "${!ORIG_PAUSED[@]}"; do
    [ "${ORIG_PAUSED[$dag]}" = true ] || continue
    api PATCH "/api/v2/dags/$dag" '{"is_paused":true}' >/dev/null && echo "re-paused $dag"
    discard_scheduled_runs "$dag" "$STARTED"
  done
  stop_port_forward
  exit $rc
}
trap cleanup EXIT

# ---- helpers ------------------------------------------------------------------------------------------
upload() { # NDJSON lines on stdin -> prints the new object generation
  curl -sf -X POST --data-binary @- -H 'Content-Type: application/x-ndjson' \
    "$GCS/upload/storage/v1/b/$BUCKET/o?uploadType=media&name=$(jq -rn --arg o "$OBJECT" '$o|@uri')" |
    jq -r .generation
}
returns_file() { # count amount-prefix -> NDJSON of `count` return lines on $DAY
  local i
  for i in $(seq "$1"); do
    printf '{"return_id":"P5-%s","order_id":"O-%s","returned_at":"%sT%02d:00:00+00:00","amount":"%s.%02d","reason":"check"}\n' \
      "$i" "$i" "$DAY" "$i" "$2" "$i"
  done
}
# Publish the exact notification fake-gcs sends, as Pub/Sub would on a redelivery.
republish() { # generation
  local attrs
  attrs=$(jq -cn --arg b "$BUCKET" --arg o "$OBJECT" --arg g "$1" \
    '{bucketId:$b, objectId:$o, objectGeneration:$g, eventType:"OBJECT_FINALIZE", payloadFormat:"JSON_API_V1"}')
  curl -sf -X POST -H 'Content-Type: application/json' \
    -d "{\"messages\":[{\"attributes\":$attrs,\"data\":\"$(printf '{}' | base64)\"}]}" \
    "$PUBSUB/topics/gcs-object-events:publish" >/dev/null || fail "could not publish to the emulator"
}
runs_for() { # generation -> "run_id state" lines of producer runs carrying that generation
  api GET "/api/v2/dags/$PRODUCER/dagRuns?limit=100&order_by=-start_date" |
    jq -r --arg g "$1" '.dag_runs[] | select(.conf.generation == $g) | "\(.dag_run_id) \(.state)"'
}
# Wait until exactly one producer run carries the generation and it has finished successfully.
wait_one_run() { # generation [timeout] -> prints the run id
  local gen=$1 end=$((SECONDS + ${2:-300})) lines n state
  while [ $SECONDS -lt $end ]; do
    lines=$(runs_for "$gen")
    n=$(grep -c . <<<"$lines" || true)
    [ "$n" -gt 1 ] && fail "generation $gen started $n runs: $lines"
    state=${lines##* }
    [ "$state" = failed ] && fail "run for generation $gen failed: $lines"
    [ "$n" = 1 ] && [ "$state" = success ] && { echo "${lines%% *}"; return 0; }
    sleep 3
  done
  fail "no successful run for generation $gen within the timeout (saw: ${lines:-none})"
}
ti_states() { # dag run -> "task=state ..." sorted
  api GET "/api/v2/dags/$1/dagRuns/$(jq -rn --arg r "$2" '$r|@uri')/taskInstances?limit=100" |
    jq -r '[.task_instances[] | "\(.task_id)=\(.state)"] | sort | join(" ")'
}
ti_state() { # dag run task -> state
  api GET "/api/v2/dags/$1/dagRuns/$(jq -rn --arg r "$2" '$r|@uri')/taskInstances/$3" | jq -r .state
}
loaded() { # -> "rows:generation" of the object in ds_source
  psql_wh "SELECT count(*) || ':' || coalesce(max(_generation)::text, '-') || ':' || count(DISTINCT _generation)
           FROM ds_source.partner_returns WHERE _source_uri = 'gs://$BUCKET/$OBJECT'"
}
adapter_saw() { # outcome generation since -> number of adapter log lines with that outcome
  wk logs deploy/event-adapter --since-time="$3" |
    grep -c "\"outcome\": \"$1\".*\"generation\": \"$2\"" || true
}

# ---- setup --------------------------------------------------------------------------------------------
wk rollout status deployment/event-adapter --timeout=120s >/dev/null || fail "event adapter is not rolled out"
curl -sf -o /dev/null "$PUBSUB/topics/gcs-object-events" || fail "topic gcs-object-events missing (make services-up)"
start_port_forward
refresh_token
for dag in "$PRODUCER" "$CONSUMER"; do
  wait_dag_ready "$dag"
  ORIG_PAUSED[$dag]=$(api GET "/api/v2/dags/$dag" | jq -r .is_paused)
  api PATCH "/api/v2/dags/$dag" '{"is_paused":false}' >/dev/null
done
# Fixture: the consumer's exposed.net_sales_daily reads gold.daily_sales for $DAY, which only a
# sales_elt run for the interval [$DAY, +1 day) builds. A fresh lab (CI) has none, so build it with
# the real producer, then remove the readiness rows that run recorded: the deferral step below needs
# sales.gold not ready for exactly that interval, and these rows are the check's own.
daily_sales_rows() { psql_wh "SELECT count(*) FROM gold.daily_sales WHERE order_date = '$DAY'" 2>/dev/null || echo 0; }
if [ "$(daily_sales_rows)" = 0 ]; then
  wait_dag_ready sales_elt
  ORIG_PAUSED[sales_elt]=$(api GET /api/v2/dags/sales_elt | jq -r .is_paused)
  api PATCH /api/v2/dags/sales_elt '{"is_paused":false}' >/dev/null
  fixture_run="phase5__fixture__$(date +%s)"
  api POST /api/v2/dags/sales_elt/dagRuns \
    "{\"dag_run_id\":\"$fixture_run\",\"logical_date\":\"${CONSUMER_LOGICAL}T00:00:00.$(date +%N | cut -c1-6)Z\"}" >/dev/null ||
    fail "could not trigger the sales_elt fixture run"
  say "fixture: gold.daily_sales has no $DAY yet; building it with sales_elt run $fixture_run"
  end=$((SECONDS + 900))
  until state=$(api GET "/api/v2/dags/sales_elt/dagRuns/$fixture_run" | jq -r .state) &&
    [ "$state" = success ] || [ "$state" = failed ] || [ $SECONDS -ge $end ]; do sleep 10; done
  [ "$state" = success ] || fail "sales_elt fixture run $fixture_run ended $state"
  [ "$(daily_sales_rows)" != 0 ] || fail "gold.daily_sales still has no $DAY after $fixture_run"
  psql_wh "DELETE FROM ops.readiness WHERE run_id = '$fixture_run'" >/dev/null
fi

# The consumer's interval must start with nothing ready. Rows this check wrote earlier are reset;
# a sales.gold row from a real sales_elt run is never touched, so then the check refuses to run.
# The producer's file ledger is not reset, because every upload below is a new generation.
in_interval="interval_start = '$INTERVAL_START' AND interval_end = '$INTERVAL_END'"
psql_wh "DELETE FROM ops.readiness WHERE $in_interval
         AND (product IN ('returns.bronze', 'returns.silver', 'finance.exposed') OR run_id = 'phase5-check')" >/dev/null
real=$(psql_wh "SELECT run_id FROM ops.readiness WHERE $in_interval AND product = 'sales.gold'")
[ -z "$real" ] || fail "sales.gold is already recorded for $DAY by $real; the deferral step needs an interval sales_elt has not built"

# ---- (e, part 1) the consumer defers while its producers are not ready ----------------------------
CONSUMER_RUN="phase5__finance__$(date +%s)"
api POST "/api/v2/dags/$CONSUMER/dagRuns" \
  "{\"dag_run_id\":\"$CONSUMER_RUN\",\"logical_date\":\"${CONSUMER_LOGICAL}T00:00:00.$(date +%N | cut -c1-6)Z\"}" >/dev/null ||
  fail "could not trigger $CONSUMER"
say "(e) triggered $CONSUMER_RUN for [$INTERVAL_START, $INTERVAL_END)"
end=$((SECONDS + 180))
until [ "$(ti_state "$CONSUMER" "$CONSUMER_RUN" wait_sales_gold)" = deferred ] &&
  [ "$(ti_state "$CONSUMER" "$CONSUMER_RUN" wait_returns_silver)" = deferred ]; do
  [ $SECONDS -lt $end ] || fail "consumer waits never deferred: $(ti_states "$CONSUMER" "$CONSUMER_RUN")"
  sleep 3
done
pool=$(api GET /api/v2/pools/default_pool | jq -r '"running=\(.running_slots) deferred=\(.deferred_slots) occupied=\(.occupied_slots)"')
echo "ok: (e) both waits deferred to the triggerer; default_pool $pool"

# ---- (a) one file -> exactly one scoped run ----------------------------------------------------------
SINCE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
GEN1=$(returns_file 3 1 | upload) || fail "upload failed"
say "(a) uploaded gs://$BUCKET/$OBJECT generation $GEN1 (3 lines)"
RUN1=$(wait_one_run "$GEN1")
[ "$(loaded)" = "3:$GEN1:1" ] || fail "ds_source after (a) is $(loaded), expected 3:$GEN1:1"
[ "$(psql_wh "SELECT rows FROM ops.file_loads WHERE object = '$OBJECT' AND generation = $GEN1")" = 3 ] ||
  fail "ops.file_loads has no 3-row entry for generation $GEN1"
echo "ok: (a) exactly one run $RUN1 ($(ti_states "$PRODUCER" "$RUN1" | grep -o 'success' | wc -l) tasks success); ds_source rows:generation $(loaded)"

# ---- (b) a redelivered event is a no-op ---------------------------------------------------------------
republish "$GEN1"
say "(b) republished the event for generation $GEN1"
end=$((SECONDS + 60))
until [ "$(adapter_saw duplicate "$GEN1" "$SINCE")" -ge 1 ]; do
  [ $SECONDS -lt $end ] || fail "adapter never reported the redelivery as duplicate"
  sleep 2
done
[ "$(runs_for "$GEN1" | grep -c .)" = 1 ] || fail "redelivery started another run: $(runs_for "$GEN1")"
[ "$(loaded)" = "3:$GEN1:1" ] || fail "ds_source changed after the redelivery: $(loaded)"
echo "ok: (b) redelivery answered 409 (adapter: duplicate, acked); still one run, ds_source $(loaded)"

# ---- (c) redelivery after the run is gone from Airflow: the durable ledger makes it a no-op -----------
api DELETE "/api/v2/dags/$PRODUCER/dagRuns/$(jq -rn --arg r "$RUN1" '$r|@uri')" >/dev/null || fail "could not delete $RUN1"
republish "$GEN1"
say "(c) deleted $RUN1 and republished generation $GEN1"
RUN1B=$(wait_one_run "$GEN1")
states=$(ti_states "$PRODUCER" "$RUN1B")
for expected in not_loaded_yet=success load=skipped record_file=skipped; do
  grep -qw "$expected" <<<"$states" || fail "re-created run did not short-circuit ($expected): $states"
done
[ "$(loaded)" = "3:$GEN1:1" ] || fail "ds_source changed after the ledger short-circuit: $(loaded)"
echo "ok: (c) re-created run $RUN1B short-circuited on ops.file_loads (load=skipped); ds_source $(loaded)"

# ---- (d) a new generation of the same object is a new, replacing run ----------------------------------
GEN2=$(returns_file 2 7 | upload) || fail "upload failed"
say "(d) re-uploaded $OBJECT as generation $GEN2 (2 lines)"
RUN2=$(wait_one_run "$GEN2")
[ "$(loaded)" = "2:$GEN2:1" ] || fail "ds_source after (d) is $(loaded), expected 2:$GEN2:1 (replaced, not added)"
[ "$(psql_wh "SELECT count(*) FROM silver.returns WHERE _source_uri = 'gs://$BUCKET/$OBJECT'")" = 2 ] ||
  fail "silver.returns does not hold exactly the 2 rows of generation $GEN2"
echo "ok: (d) one run $RUN2 for the new generation; rows replaced, ds_source $(loaded)"

# ---- (e, part 2) the consumer resumes once every producer is ready -------------------------------------
[ "$(ti_state "$CONSUMER" "$CONSUMER_RUN" wait_returns_silver)" = success ] ||
  fail "wait_returns_silver did not finish after returns.silver became ready"
[ "$(ti_state "$CONSUMER" "$CONSUMER_RUN" wait_sales_gold)" = deferred ] ||
  fail "wait_sales_gold should still be deferred (sales.gold not ready)"
# Stand in for sales_elt finishing gold for the interval: the consumer only ever reads the ledger.
psql_wh "INSERT INTO ops.readiness (product, interval_start, interval_end, watermark, run_id, status)
         VALUES ('sales.gold', '$INTERVAL_START', '$INTERVAL_END', '$INTERVAL_END', 'phase5-check', 'ready')" >/dev/null
say "(e) recorded sales.gold ready for the interval"
end=$((SECONDS + 600))
while :; do
  state=$(api GET "/api/v2/dags/$CONSUMER/dagRuns/$CONSUMER_RUN" | jq -r .state)
  [ "$state" = success ] && break
  [ "$state" = failed ] && fail "$CONSUMER_RUN failed: $(ti_states "$CONSUMER" "$CONSUMER_RUN")"
  [ $SECONDS -lt $end ] || fail "$CONSUMER_RUN is '$state' after 600s"
  sleep 5
done
net=$(psql_wh "SELECT revenue_eur || ' - ' || returns_eur || ' = ' || net_revenue_eur || ' (' || returns_count || ' returns)'
              FROM exposed.net_sales_daily WHERE order_date = '$DAY'")
expected=$(psql_wh "SELECT sum(amount) FROM silver.returns WHERE return_date = '$DAY'")
[ -n "$net" ] && [[ $net == *" - $expected = "* ]] || fail "exposed.net_sales_daily[$DAY] is '$net'; expected returns of $expected"
[ "$(psql_wh "SELECT status FROM ops.readiness WHERE product = 'finance.exposed' AND interval_start = '$INTERVAL_START'")" = ready ] ||
  fail "finance.exposed is not ready"
echo "ok: (e) $CONSUMER_RUN resumed and succeeded; finance.exposed ready; exposed.net_sales_daily[$DAY]: $net"

echo "phase5-check passed"
