#!/usr/bin/env bash
# Reconcile Airflow's history with the warehouse after a metadata DB restore (runbook drill 10, PLAN D32).
# Lists the DAG runs that wrote ops.readiness rows in the last 7 days but that the metadata DB no
# longer knows (what AirflowMetadataBehindWarehouse alerts on); with --replay, re-creates each one.
#   - A manual or event run is replayed under its original run id, so the ledger's (dag_id, run_id)
#     matches again. Every business task is idempotent per run id and interval (D15), so the replay
#     rewrites the same rows; a file-arrival run gets its event back from ops.file_loads (D18) and
#     short-circuits on it, loading nothing.
#   - A scheduled run (scheduled__...) is replayed as a manual run with a new id for the same
#     interval, never under its own id: that id belongs to the run the scheduler creates for the
#     interval, and a manual run holding it would collide with it. The replay rewrites the rows
#     under the new id.
#   - Replays run one at a time, in the order the lost runs finished, each waiting for the last:
#     a replayed consumer finds its producers' readiness rows already `ready` (the lost runs left
#     them), so replayed together it would build before its producers are rebuilt.
# Usage: scripts/metadata-reconcile.sh [--replay]
# Prints one line per lost run: dag_id run_id interval_end products [-> replayed as <run id>].
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
# Its own port, so a check that holds the usual one (drill 10) can call it.
API_PORT=${API_PORT:-18081}
# shellcheck source=../tests/e2e/lib/airflow-api.sh
source "$REPO/tests/e2e/lib/airflow-api.sh"
REPLAY=""
case "${1:-}" in
  --replay) REPLAY=1 ;;
  "") ;;
  *) fail "usage: $0 [--replay]" ;;
esac
psql_wh() { # stdin closed: `exec -T` forwards it, and inside the loop below it would eat the loop's input
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d warehouse -v ON_ERROR_STOP=1 -AtF ' ' -c "$1" </dev/null
}
run_path() { echo "/api/v2/dags/$1/dagRuns/$(jq -rn --arg r "$2" '$r|@uri')"; }
known() { api GET "$(run_path "$1" "$2")" >/dev/null 2>&1; } # dag_id run_id
wait_done() { # dag_id run_id -> prints the final state; a replay is a whole pipeline run
  local end=$((SECONDS + 1800)) state=""
  while [ $SECONDS -lt $end ]; do
    state=$(api GET "$(run_path "$1" "$2")" | jq -r .state)
    case "$state" in success | failed) echo "$state"; return 0 ;; esac
    sleep 5
  done
  fail "$1 run $2 is still $state after 30 min"
}

ensure_port_forward
refresh_token

lost=0
# Runs that wrote rows in the same window as the alert, in the order they finished (last row written).
while read -r dag run end products; do
  known "$dag" "$run" && continue
  lost=$((lost + 1))
  line="$dag $run $end $products"
  if [ -n "$REPLAY" ]; then
    # A manual run's interval is the schedule's interval ending at its logical date (pplk8s.context);
    # the microseconds keep the logical date unique per DAG.
    body=$(jq -cn --arg end "${end}.$(date +%N | cut -c1-6)Z" '{logical_date: $end, conf: {}}')
    case "$run" in
      scheduled__*) ;;
      *) body=$(jq -c --arg id "$run" '. + {dag_run_id: $id}' <<<"$body") ;;
    esac
    event=$(psql_wh "SELECT json_build_object('bucket', bucket, 'object', object, 'generation', generation::text)
                     FROM ops.file_loads WHERE run_id = '${run//\'/\'\'}'")
    [ -z "$event" ] || body=$(jq -c --argjson e "$event" '.conf = $e' <<<"$body")
    [ "$(api GET "/api/v2/dags/$dag" | jq -r .is_paused)" = false ] || fail "$dag is paused; unpause it to replay $run"
    new=$(api POST "/api/v2/dags/$dag/dagRuns" "$body" | jq -r .dag_run_id) || fail "could not replay $dag $run"
    state=$(wait_done "$dag" "$new")
    line+=" -> replayed as $new: $state"
    [ "$state" = success ] || { echo "$line"; fail "the replay of $dag $run failed; fix it before replaying the runs after it"; }
  fi
  echo "$line"
done < <(psql_wh "SELECT dag_id, run_id, to_char(max(interval_end) AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS'),
                         string_agg(product, ',' ORDER BY product)
                  FROM ops.readiness
                  WHERE dag_id IS NOT NULL AND updated_at > now() - interval '7 days'
                  GROUP BY dag_id, run_id ORDER BY max(updated_at)")
[ "$lost" -gt 0 ] || echo "every run that wrote ops.readiness in the last 7 days is known to Airflow"
