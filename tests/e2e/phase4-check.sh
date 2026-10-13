#!/usr/bin/env bash
# Phase 4 exit check (PLAN.md): a full sales_elt run succeeds; clearing and re-running any task or the
# whole run duplicates no data; killing a mapped extract task mid-run recovers via retry.
# Also rehearses the FAIL_RATE retry drill. Expects `make airflow-up workloads-up` to have run.
# Re-runnable: every run gets a fresh dag_run_id, all runs process the same 1-day interval, and the
# EL Factory ConfigMap and the DAG's paused flag are restored on exit.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/airflow-api.sh
source "$(dirname "$0")/lib/airflow-api.sh"
DAG=sales_elt
LOGICAL_DAY=2026-10-02 # a manual run on this logical date processes [2026-10-01, 2026-10-02)
INTERVAL_START='2026-10-01 00:00:00+00'
INTERVAL_END='2026-10-02 00:00:00+00'
wk() { kubectl --context "$CTX" -n workloads "$@"; }
psql_wh() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d warehouse -Atc "$1"
}
now() { date +%T; }
say() { echo "[$(now)] $*"; }

# ---- restorable state: EL Factory config and the DAG paused flag -----------------------------------
ORIG_PAGE_SIZE=$(wk get cm el-factory-config -o jsonpath='{.data.PAGE_SIZE}')
ORIG_FAIL_RATE=$(wk get cm el-factory-config -o jsonpath='{.data.FAIL_RATE}')
ORIG_PAUSED=""
set_elf_config() { # PAGE_SIZE FAIL_RATE
  wk patch cm el-factory-config --type merge -p "{\"data\":{\"PAGE_SIZE\":\"$1\",\"FAIL_RATE\":\"$2\"}}" >/dev/null
  wk rollout restart deployment/el-factory >/dev/null
  wk rollout status deployment/el-factory --timeout=180s >/dev/null || fail "el-factory rollout"
}
cleanup() {
  local rc=$?
  set +e
  if [ "$(wk get cm el-factory-config -o jsonpath='{.data.PAGE_SIZE}/{.data.FAIL_RATE}')" != "$ORIG_PAGE_SIZE/$ORIG_FAIL_RATE" ]; then
    set_elf_config "$ORIG_PAGE_SIZE" "$ORIG_FAIL_RATE"
    echo "restored el-factory-config (PAGE_SIZE=$ORIG_PAGE_SIZE FAIL_RATE=$ORIG_FAIL_RATE)"
  fi
  if [ "$ORIG_PAUSED" = true ] && [ -n "$TOKEN" ]; then
    api PATCH "/api/v2/dags/$DAG" '{"is_paused":true}' >/dev/null && echo "re-paused $DAG"
  fi
  stop_port_forward
  exit $rc
}
trap cleanup EXIT

# ---- Airflow helpers --------------------------------------------------------------------------------
dag_path() { echo "/api/v2/dags/$DAG/dagRuns/$1"; }
run_state() { api GET "$(dag_path "$1")" | jq -r .state; }
ti() { api GET "$(dag_path "$1")/taskInstances/$2"; } # run task[/map_index]

trigger_run() { # label -> prints dag_run_id
  local id ns
  id="phase4__$1__$(date +%s)"
  ns=$(date +%N | cut -c1-6)
  api POST "/api/v2/dags/$DAG/dagRuns" \
    "{\"dag_run_id\":\"$id\",\"logical_date\":\"${LOGICAL_DAY}T00:00:00.${ns}Z\"}" >/dev/null ||
    fail "could not trigger $DAG"
  echo "$id"
}

# Wait until the run is `success` and every task instance is `success`; $2 = timeout in seconds.
wait_success() {
  local run=$1 limit=${2:-600} end state bad
  end=$((SECONDS + limit))
  while [ $SECONDS -lt $end ]; do
    state=$(run_state "$run")
    bad=$(api GET "$(dag_path "$run")/taskInstances?limit=200" |
      jq '[.task_instances[]|select(.state!="success")]|length')
    [ "$state" = success ] && [ "$bad" = 0 ] && return 0
    [ "$state" = failed ] && fail "run $run failed"
    sleep 3
  done
  fail "run $run is '$state' after ${limit}s"
}

clear_tasks() { # run json-array-of-task_ids [include_downstream]
  api POST "/api/v2/dags/$DAG/clearTaskInstances" \
    "{\"dag_run_id\":\"$1\",\"task_ids\":$2,\"only_failed\":false,\"include_downstream\":${3:-false},\"dry_run\":false}" >/dev/null ||
    fail "could not clear $2 in $1"
}

# Wait for a task instance to run again after a clear: its try_number must pass $3, then the run must be green.
wait_rerun() { # run task[/map] previous_try_number
  local run=$1 end
  end=$((SECONDS + 300))
  while [ "$(ti "$run" "$2" | jq .try_number)" -le "$3" ]; do
    [ $SECONDS -lt $end ] || fail "$2 never re-ran"
    sleep 2
  done
  wait_success "$run" 300
}

# ---- warehouse snapshots ----------------------------------------------------------------------------
ds_counts() { # run_id -> "customers=rows/distinct orders=rows/distinct" (distinct exposes duplicates)
  psql_wh "SELECT 'customers=' || count(*) || '/' || count(DISTINCT customer_id) FROM ds_source.synthetic_customers WHERE _run_id = '$1'
           UNION ALL
           SELECT 'orders=' || count(*) || '/' || count(DISTINCT order_id) FROM ds_source.synthetic_orders WHERE _run_id = '$1'" |
    paste -sd' '
}
layer_sig() { # row count and content hash of every gold/exposed table
  local t out=""
  for t in gold.daily_sales gold.customer_lifetime gold.daily_weather exposed.sales_by_country_daily exposed.daily_sales_with_weather; do
    out+="$t=$(psql_wh "SELECT count(*) || ':' || coalesce(md5(string_agg(x::text, '|' ORDER BY x::text)), '-') FROM $t x") "
  done
  echo "$out"
}
readiness_rows() { # run_id -> products ready for this interval written by that run
  psql_wh "SELECT product FROM ops.readiness WHERE interval_start = '$INTERVAL_START' AND interval_end = '$INTERVAL_END'
           AND run_id = '$1' AND status = 'ready' ORDER BY product" | paste -sd' '
}
EXPECTED_PRODUCTS="sales sales.bronze sales.exposed sales.gold sales.silver"

# ---- setup ------------------------------------------------------------------------------------------
wk rollout status deployment/el-factory --timeout=120s >/dev/null || fail "el-factory is not rolled out"
[ "$ORIG_FAIL_RATE" = 0 ] || fail "FAIL_RATE is $ORIG_FAIL_RATE; run with the declared config (0)"
start_port_forward
refresh_token
wait_dag_ready "$DAG"
ORIG_PAUSED=$(api GET "/api/v2/dags/$DAG" | jq -r .is_paused)
api PATCH "/api/v2/dags/$DAG" '{"is_paused":false}' >/dev/null

# ---- (a) a full run succeeds ------------------------------------------------------------------------
RUN=$(trigger_run full)
say "(a) triggered $RUN"
wait_success "$RUN" 600
BASE_COUNTS=$(ds_counts "$RUN")
BASE_SIG=$(layer_sig)
# Both entities must be loaded (rows > 0) with no duplicate keys (rows == distinct keys).
[ "$(tr ' ' '\n' <<<"$BASE_COUNTS" | sed -E 's/.*=([0-9]+)\/([0-9]+)/\1 \2/' |
  awk '$1 > 0 && $1 == $2' | wc -l)" = 2 ] || fail "unexpected ds_source counts for $RUN: $BASE_COUNTS"
[ "$(readiness_rows "$RUN")" = "$EXPECTED_PRODUCTS" ] || fail "ops.readiness for $RUN: '$(readiness_rows "$RUN")'"
echo "ok: (a) full run $RUN succeeded"
echo "    ds_source rows/distinct keys: $BASE_COUNTS"
echo "    gold/exposed (count:hash): $BASE_SIG"
echo "    ops.readiness ready: $(readiness_rows "$RUN")"

assert_unchanged() { # what
  local counts sig
  counts=$(ds_counts "$RUN")
  sig=$(layer_sig)
  [ "$counts" = "$BASE_COUNTS" ] || fail "$1 changed ds_source rows: $BASE_COUNTS -> $counts"
  [ "$sig" = "$BASE_SIG" ] || fail "$1 changed gold/exposed: $BASE_SIG -> $sig"
  [ "$(readiness_rows "$RUN")" = "$EXPECTED_PRODUCTS" ] || fail "$1 broke ops.readiness"
  echo "ok: (b) $1: ds_source, gold/exposed and ops.readiness unchanged"
}

# ---- (b) clear and re-run: a single extract map index, a dbt stage, the whole run ----------------------
tries=$(ti "$RUN" extract/1 | jq .try_number)
clear_tasks "$RUN" '[["extract",1]]'
wait_rerun "$RUN" extract/1 "$tries"
assert_unchanged "re-running extract map index 1"

tries=$(ti "$RUN" stage_gold.dbt_gold | jq .try_number)
# Downstream too: rebuilding a gold table drops the exposed views that depend on it (dbt-postgres
# drops the old relation with CASCADE), so a gold-only re-run is incomplete until exposed re-runs.
clear_tasks "$RUN" '["stage_gold.dbt_gold"]' true
wait_rerun "$RUN" stage_gold.dbt_gold "$tries"
assert_unchanged "re-running dbt_gold"

tries=$(ti "$RUN" extract/0 | jq .try_number)
api POST "$(dag_path "$RUN")/clear" '{"dry_run":false}' >/dev/null || fail "could not clear the run"
wait_rerun "$RUN" extract/0 "$tries"
assert_unchanged "clearing and re-running the whole run"

# ---- (c) kill a worker mid-extract: the mapped task recovers via retry --------------------------------
say "(c) PAGE_SIZE=1 so a mapped extract spans hundreds of pages and can be caught in flight"
set_elf_config 1 0
kill_drill() { # one attempt; returns 1 if the task finished before it could be killed
  local run caught host pod try seen last="" j end
  run=$(trigger_run kill)
  end=$((SECONDS + 90))
  caught=""
  while [ $SECONDS -lt $end ] && [ -z "$caught" ]; do
    caught=$(api GET "$(dag_path "$run")/taskInstances?task_id=extract&limit=10" |
      jq -c '[.task_instances[]|select(.state=="running" and .hostname != "")]|first // empty')
    [ -n "$caught" ] || sleep 0.2
  done
  [ -n "$caught" ] || { api GET "$(dag_path "$run")" >/dev/null; wait_success "$run" 300; return 1; }
  j=$(jq -r .map_index <<<"$caught")
  try=$(jq -r .try_number <<<"$caught")
  host=$(jq -r .hostname <<<"$caught")
  pod=${host%%.*}
  say "    extract[$j] try $try running on $pod; killing the pod (SIGKILL, no grace)"
  kc delete pod "$pod" --grace-period=0 --force >/dev/null 2>&1 || fail "could not delete $pod"
  end=$((SECONDS + 900))
  while [ $SECONDS -lt $end ]; do
    seen=$(ti "$run" "extract/$j" | jq -r '"\(.state) try \(.try_number)"')
    [ "$seen" = "$last" ] || { say "    extract[$j]: $seen"; last=$seen; }
    [ "$(run_state "$run")" = success ] && break
    sleep 5
  done
  wait_success "$run" 300
  KILL_RUN=$run
  KILL_FINAL_TRY=$(ti "$run" "extract/$j" | jq .try_number)
  KILL_FIRST_TRY=$try
  KILL_MAP=$j
  KILL_FIRST_STATE=$(api GET "$(dag_path "$run")/taskInstances/extract/$j/tries" |
    jq -r --argjson t "$try" '.task_instances[]|select(.try_number==$t)|.state')
  [ "$KILL_FINAL_TRY" -gt "$KILL_FIRST_TRY" ] # the kill really interrupted a try
}
killed=false
for attempt in 1 2 3 4 5; do
  if kill_drill; then killed=true; break; fi
  say "    attempt $attempt finished before the pod could be killed; retrying with a new run"
done
$killed || fail "could not kill a mapped extract mid-flight in 5 attempts"
wk rollout status deployment/el-factory --timeout=60s >/dev/null
kc rollout status statefulset/airflow-worker --timeout=300s >/dev/null || fail "worker pods not Ready"
KILL_COUNTS=$(ds_counts "$KILL_RUN")
[ "$KILL_COUNTS" = "$BASE_COUNTS" ] || fail "after the kill ds_source has $KILL_COUNTS, expected $BASE_COUNTS"
[ "$(layer_sig)" = "$BASE_SIG" ] || fail "gold/exposed changed after the kill drill"
[ "$KILL_FIRST_STATE" != success ] || fail "killed try is recorded as success"
echo "ok: (c) extract[$KILL_MAP] try $KILL_FIRST_TRY (killed, recorded as '$KILL_FIRST_STATE') -> try $KILL_FINAL_TRY success"
echo "    run $KILL_RUN succeeded; ds_source $KILL_COUNTS; gold/exposed unchanged"

# ---- (d) FAIL_RATE drill: retryable 503s are retried by Airflow -------------------------------------
say "(d) FAIL_RATE=1: every /extract answers a retryable 503 until we lift it"
set_elf_config 100 1
RUN=$(trigger_run failrate)
end=$((SECONDS + 240))
until [ "$(api GET "$(dag_path "$RUN")/taskInstances?task_id=extract&limit=10" |
  jq '[.task_instances[]|select(.try_number>=2)]|length')" -ge 1 ]; do
  [ $SECONDS -lt $end ] || fail "no extract retry observed under FAIL_RATE=1"
  sleep 3
done
retry_log=$(api GET "$(dag_path "$RUN")/taskInstances/extract/logs/1?map_index=0" |
  jq -r '.content[]|tostring' | grep -om1 'POST /extract: HTTP 503: [^"]*') ||
  fail "try 1 log has no HTTP 503 line"
say "    try 1 failed with: ${retry_log:0:160}"
say "    retries observed; lifting FAIL_RATE"
set_elf_config 100 0
wait_success "$RUN" 600
for m in 0 1; do
  t=$(ti "$RUN" "extract/$m" | jq .try_number)
  [ "$t" -ge 2 ] || [ "$m" = 1 ] || fail "extract[0] did not retry"
done
[ "$(ds_counts "$RUN")" = "$BASE_COUNTS" ] || fail "FAIL_RATE run has $(ds_counts "$RUN"), expected $BASE_COUNTS"
[ "$(layer_sig)" = "$BASE_SIG" ] || fail "gold/exposed changed after the FAIL_RATE drill"
echo "ok: (d) retryable 503s were retried by Airflow (extract[0] try_number $(ti "$RUN" extract/0 | jq .try_number), extract[1] try_number $(ti "$RUN" extract/1 | jq .try_number)); run succeeded, counts unchanged"

echo "phase4-check passed"
