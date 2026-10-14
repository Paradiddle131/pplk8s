#!/usr/bin/env bash
# Phase 8 exit check (PLAN.md, D34-D36, issue #58): run tlc_monthly on the lab for its scheduled
# months, backfill the drift months, and assert for every month that
#   - ops.readiness holds tlc.exposed as ready,
#   - bronze (the month's current file version) = silver + quarantine, quarantine under 10 %,
#   - silver's cbd_congestion_fee is NULL before 2025-01 and populated from 2025-01 on (yellow),
# that the 2023-01 backfill widened the yellow landing table (the 2023 retype, D34; #82),
# then forge an older version of one month's file and re-run it: the real file replaces the month.
# Downloads real TLC files (~60 MB a yellow month). Expects `make airflow-up workloads-up`.
# Re-runnable: months that already succeeded are not re-run (backfills reprocess failed runs only),
# and on exit the DAG's paused flag is restored. Scheduled runs stay: they are the DAG's real
# schedule, and a month that is not published yet keeps waiting deferrably (D35).
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/airflow-api.sh
source "$(dirname "$0")/lib/airflow-api.sh"
DAG=tlc_monthly
FIRST_SCHEDULED=2026-06 # tlc_monthly's START
# D35's drift months, one per schema seam (#73, #82), as backfill ranges (one active backfill per DAG at
# a time): 2023-01 is the only 2023 month with the old types and `airport_fee`, 2025-01 adds
# `cbd_congestion_fee`, 2026-06 adds `request_source` (the schedule's catchup already runs 2026-06).
BACKFILLS=("2023-01 2023-01" "2025-01 2025-01")
DRIFT_MONTHS=(2023-01 2025-01 2026-06)
REPUBLISH_ENTITY=green # the smallest file (~1 MB), so the replay is quick
MONTH_TIMEOUT=${MONTH_TIMEOUT:-3600}
WAREHOUSE_CEILING_GB=${WAREHOUSE_CEILING_GB:-15} # D35; a warning until retention (#87) lands
FORGED='"phase8-forged"'
psql_wh() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d warehouse -v ON_ERROR_STOP=1 -Atc "$1"
}
say() { echo "[$(date +%T)] $*"; }

ORIG_PAUSED=""
cleanup() {
  local rc=$?
  set +e
  [ "$ORIG_PAUSED" = true ] && api PATCH "/api/v2/dags/$DAG" '{"is_paused":true}' >/dev/null && echo "re-paused $DAG"
  stop_port_forward
  exit $rc
}
trap cleanup EXIT

# ---- helpers ------------------------------------------------------------------------------------------
month_start() { echo "$1-01T00:00:00Z"; } # YYYY-MM -> the run's logical date
next_month() { date -u -d "$1-01 +1 month" +%Y-%m; }
months_between() { # first last (YYYY-MM, inclusive) -> one month per line
  local m=$1
  while [[ $m < $2 || $m == "$2" ]]; do echo "$m"; m=$(next_month "$m"); done
}
run_of() { # YYYY-MM -> "run_id state" of the run whose logical date starts that month, or nothing
  api GET "/api/v2/dags/$DAG/dagRuns?logical_date_gte=$(month_start "$1")&logical_date_lte=$(month_start "$1")&limit=5" |
    jq -r '.dag_runs[] | "\(.dag_run_id) \(.state)"'
}
run_path() { echo "/api/v2/dags/$DAG/dagRuns/$(jq -rn --arg r "$1" '$r|@uri')"; }
ti_states() { # run -> "task[map]=state ..." sorted
  api GET "$(run_path "$1")/taskInstances?limit=200" |
    jq -r '[.task_instances[] | "\(.task_id)\(if .map_index >= 0 then "[\(.rendered_map_index // .map_index)]" else "" end)=\(.state)"] | sort | join(" ")'
}
waiting_for_publication() { # run -> 0 when every unfinished task is a deferred wait_published (or downstream of one)
  local states
  states=$(api GET "$(run_path "$1")/taskInstances?limit=200" | jq -r '.task_instances[] | "\(.task_id) \(.state)"')
  grep -q '^wait_published deferred$' <<<"$states" &&
    ! grep -qE '^(extract|stage_[a-z]+\.[a-z_]+) (running|success|failed|up_for_retry)$' <<<"$states"
}
# Wait until the month's run succeeded, or (allow_wait=1) is parked on an unpublished file.
# Prints "success" or "waiting".
wait_month() { # YYYY-MM allow_wait
  local end=$((SECONDS + MONTH_TIMEOUT)) line run state
  while [ $SECONDS -lt $end ]; do
    line=$(run_of "$1")
    run=${line%% *} state=${line##* }
    case "$state" in
      success) echo success; return 0 ;;
      failed) fail "$1: run $run failed: $(ti_states "$run")" ;;
    esac
    if [ -n "$run" ] && [ "$2" = 1 ] && waiting_for_publication "$run"; then echo waiting; return 0; fi
    sleep 15
    ensure_port_forward
    refresh_token
  done
  fail "$1: run ${run:-none} is '${state:-missing}' after ${MONTH_TIMEOUT}s${run:+: $(ti_states "$run")}"
}
# The month's rows in each layer, counting bronze only for the month's current file version, the one
# silver reads (the latest completed version in ops.file_versions).
layer_counts() { # YYYY-MM -> "bronze silver quarantine"
  psql_wh "
    WITH current_version AS (
      SELECT DISTINCT ON (source_uri) source_uri, etag FROM ops.file_versions
      WHERE source_uri LIKE '%_tripdata_$1.parquet' ORDER BY source_uri, completed_at DESC
    ), bronze AS (
      SELECT _source_uri, _etag FROM bronze.tlc_yellow_trips WHERE data_month = '$1'
      UNION ALL SELECT _source_uri, _etag FROM bronze.tlc_green_trips WHERE data_month = '$1'
    )
    SELECT (SELECT count(*) FROM bronze JOIN current_version
              ON current_version.source_uri = bronze._source_uri AND current_version.etag = bronze._etag)
      || ' ' || (SELECT count(*) FROM silver.tlc_trips WHERE data_month = '$1')
      || ' ' || (SELECT count(*) FROM silver.tlc_trips_quarantine WHERE data_month = '$1')"
}
check_month() { # YYYY-MM -> asserts the exit criterion for one loaded month and prints its counts
  local m=$1 bronze silver quarantine ready cbd
  ready=$(psql_wh "SELECT status FROM ops.readiness WHERE product = 'tlc.exposed' AND interval_start = '$m-01 00:00:00+00'")
  [ "$ready" = ready ] || fail "$m: ops.readiness tlc.exposed is '${ready:-missing}'"
  read -r bronze silver quarantine <<<"$(layer_counts "$m")"
  [ "$bronze" -gt 0 ] || fail "$m: bronze holds no rows of the current file version"
  [ "$bronze" = $((silver + quarantine)) ] ||
    fail "$m: bronze $bronze != silver $silver + quarantine $quarantine"
  [ $((quarantine * 10)) -lt "$bronze" ] || fail "$m: quarantine $quarantine is not under 10 % of $bronze"
  cbd=$(psql_wh "SELECT count(cbd_congestion_fee) FROM silver.tlc_trips WHERE data_month = '$m' AND trip_type = 'yellow'")
  if [[ $m < 2025-01 ]]; then
    [ "$cbd" = 0 ] || fail "$m: $cbd yellow rows carry cbd_congestion_fee before the fee existed"
  else
    [ "$cbd" -gt 0 ] || fail "$m: no yellow row carries cbd_congestion_fee from 2025-01 on"
  fi
  echo "ok: $m tlc.exposed ready; bronze $bronze = silver $silver + quarantine $quarantine; yellow cbd_congestion_fee rows $cbd"
}
await_backfill() { # backfill id
  local end=$((SECONDS + MONTH_TIMEOUT * 2)) done_at
  while [ $SECONDS -lt $end ]; do
    done_at=$(api GET "/api/v2/backfills/$1" | jq -r '.completed_at // empty')
    [ -n "$done_at" ] && return 0
    sleep 15
    ensure_port_forward
    refresh_token
  done
  fail "backfill $1 did not complete within $((MONTH_TIMEOUT * 2))s"
}

# ---- setup --------------------------------------------------------------------------------------------
start_port_forward
refresh_token
wait_dag_ready "$DAG"
ORIG_PAUSED=$(api GET "/api/v2/dags/$DAG" | jq -r .is_paused)
api PATCH "/api/v2/dags/$DAG" '{"is_paused":false}' >/dev/null
say "unpaused $DAG (was paused: $ORIG_PAUSED); the scheduler catches up from $FIRST_SCHEDULED"

# ---- (a) scheduled months: every complete month since START; the newest may still be unpublished -----
LAST_COMPLETE=$(date -u -d "$(date -u +%Y-%m-01) -1 month" +%Y-%m)
mapfile -t SCHEDULED < <(months_between "$FIRST_SCHEDULED" "$LAST_COMPLETE")
# TLC publishes with a 1-3 month lag (D35), so only the newest months may wait.
LAG_FLOOR=$(date -u -d "$(date -u +%Y-%m-01) -3 month" +%Y-%m)
LOADED=()
for m in "${SCHEDULED[@]}"; do
  refresh_token
  allow_wait=0
  [[ $m < $LAG_FLOOR ]] || allow_wait=1
  for _ in $(seq 40); do [ -n "$(run_of "$m")" ] && break; sleep 3; done
  [ -n "$(run_of "$m")" ] || fail "$m: the scheduler created no run (catchup from $FIRST_SCHEDULED)"
  outcome=$(wait_month "$m" "$allow_wait")
  if [ "$outcome" = waiting ]; then
    echo "ok: (a) $m is not published yet; its run waits deferrably at wait_published"
  else
    say "(a) $m succeeded"
    LOADED+=("$m")
  fi
done
[ ${#LOADED[@]} -gt 0 ] || fail "no scheduled month loaded; the latest published month must"

# ---- (b) drift months: backfill ----------------------------------------------------------------------
# Airflow allows one active backfill per DAG; one left by an interrupted check is awaited first.
for id in $(api GET "/api/v2/backfills?dag_id=$DAG&limit=100" | jq -r '.backfills[] | select(.completed_at == null) | .id'); do
  say "(b) awaiting backfill $id, still active from an earlier run"
  await_backfill "$id"
done
for range in "${BACKFILLS[@]}"; do
  read -r first last <<<"$range"
  refresh_token
  # to_date is the last day of the range, so it covers the last month's logical date whether the
  # range is inclusive or not, and stops before the next month's.
  to=$(date -u -d "$(next_month "$last")-01 -1 day" +%Y-%m-%dT00:00:00Z)
  body=$(jq -cn --arg d "$DAG" --arg f "$(month_start "$first")" --arg t "$to" \
    '{dag_id:$d, from_date:$f, to_date:$t, reprocess_behavior:"failed", max_active_runs:2}')
  id=$(api POST /api/v2/backfills "$body" | jq -r .id) || fail "could not create the backfill $first..$last"
  say "(b) backfill $id for $first..$last"
  await_backfill "$id"
  for m in $(months_between "$first" "$last"); do
    [ "$(wait_month "$m" 0)" = success ]
    LOADED+=("$m")
  done
done
for m in "${DRIFT_MONTHS[@]}"; do
  [[ " ${LOADED[*]} " == *" $m "* ]] || fail "drift month $m was not loaded"
done

# ---- (c) every loaded month meets the exit criterion ----------------------------------------------------
for m in "${LOADED[@]}"; do check_month "$m"; done
# 2023-01 is int64 where 2024+ is int32, and double where 2024+ is int64, so loading it after the
# scheduled months must have widened the landing columns rather than failing (D34, #72, #82).
types=$(psql_wh "SELECT string_agg(column_name || ' ' || data_type, ', ' ORDER BY column_name) FROM information_schema.columns
  WHERE table_schema = 'ds_source' AND table_name = 'tlc_yellow' AND column_name IN ('vendorid', 'passenger_count')")
[ "$types" = "passenger_count double precision, vendorid bigint" ] ||
  fail "(c) the 2023-01 retype did not widen ds_source.tlc_yellow: [$types]"
echo "ok: (c) the 2023-01 backfill widened the yellow landing table [$types]"

# ---- (d) a republished file replaces its month -----------------------------------------------------------
# Make the lab believe it holds an older version of the newest loaded month's green file: relabel the
# landed rows, their chunks and the completed version with a forged etag. Re-running the month then
# finds a different etag at the source, which is exactly what a republish looks like.
M=$(printf '%s\n' "${LOADED[@]}" | sort | tail -1)
URI_LIKE="%/${REPUBLISH_ENTITY}_tripdata_$M.parquet"
REAL=$(psql_wh "SELECT etag FROM ops.file_versions WHERE source_uri LIKE '$URI_LIKE' ORDER BY completed_at DESC LIMIT 1")
[ -n "$REAL" ] || fail "(d) no completed $REPUBLISH_ENTITY version for $M"
before=$(layer_counts "$M")
psql_wh "BEGIN;
  UPDATE ds_source.tlc_$REPUBLISH_ENTITY SET _etag = '$FORGED' WHERE _source_uri LIKE '$URI_LIKE' AND _etag = '$REAL';
  UPDATE ops.file_chunks SET etag = '$FORGED' WHERE source_uri LIKE '$URI_LIKE' AND etag = '$REAL';
  UPDATE ops.file_versions SET etag = '$FORGED' WHERE source_uri LIKE '$URI_LIKE' AND etag = '$REAL';
  COMMIT;" >/dev/null
say "(d) forged $FORGED as the lab's $REPUBLISH_ENTITY $M version (real: $REAL); re-running $M"
run=$(run_of "$M"); run=${run%% *}
api POST "$(run_path "$run")/clear" '{"dry_run":false}' >/dev/null || fail "(d) could not clear $run"
sleep 5
[ "$(wait_month "$M" 0)" = success ]
[ "$(psql_wh "SELECT count(*) FROM ds_source.tlc_$REPUBLISH_ENTITY WHERE _source_uri LIKE '$URI_LIKE' AND _etag = '$FORGED'")" = 0 ] ||
  fail "(d) the forged version's landed rows were not replaced"
etags=$(psql_wh "SELECT string_agg(DISTINCT _etag, ',') FROM silver.tlc_trips WHERE data_month = '$M' AND trip_type = '$REPUBLISH_ENTITY'")
[ "$etags" = "$REAL" ] || fail "(d) silver $REPUBLISH_ENTITY $M holds etags [$etags], expected [$REAL]"
after=$(layer_counts "$M")
[ "$after" = "$before" ] || fail "(d) $M counts changed from [$before] to [$after] on replaying the same file"
check_month "$M"
echo "ok: (d) the republished $REPUBLISH_ENTITY $M replaced the forged version; counts unchanged [$after]"

# ---- storage (#73): report against D35's ceiling ----------------------------------------------------------
bytes=$(psql_wh "SELECT pg_database_size('warehouse')")
gb=$(awk -v b="$bytes" 'BEGIN { printf "%.1f", b / 1024^3 }')
if awk -v b="$bytes" -v c="$WAREHOUSE_CEILING_GB" 'BEGIN { exit !(b > c * 1024^3) }'; then
  echo "WARN: warehouse is $gb GB, over D35's $WAREHOUSE_CEILING_GB GB ceiling (retention, #87, makes this a failure)"
else
  echo "ok: warehouse is $gb GB, under D35's $WAREHOUSE_CEILING_GB GB ceiling"
fi

echo "phase8-check passed (months: $(printf '%s\n' "${LOADED[@]}" | sort | xargs))"
