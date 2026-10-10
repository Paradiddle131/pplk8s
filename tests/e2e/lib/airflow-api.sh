# Shared helpers for e2e checks that drive Airflow through its REST API (source this file).
# Provides: kc, fail, start_port_forward, refresh_token, api, wait_dag_ready. Set CTX/NS/API_PORT before sourcing to override.
CTX=${CTX:-kind-pplk8s}
NS=${NS:-airflow}
API_PORT=${API_PORT:-18080}
API=http://localhost:$API_PORT
kc() { kubectl --context "$CTX" -n "$NS" "$@"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

# A port-forward is bound to one api-server pod, so it is restarted after each rollout.
pf=""
start_port_forward() {
  [ -z "$pf" ] || kill "$pf" 2>/dev/null || true
  kc port-forward svc/airflow-api-server "$API_PORT:8080" >/dev/null 2>&1 &
  pf=$!
  for _ in $(seq 30); do curl -sf -o /dev/null "$API/api/v2/version" 2>/dev/null && return; sleep 1; done
  fail "API not reachable on $API"
}
stop_port_forward() { [ -z "$pf" ] || kill "$pf" 2>/dev/null || true; }
trap stop_port_forward EXIT
# Bash skips the EXIT trap when killed by a signal it does not trap; exiting on them runs it, so a
# check's cleanup (restoring config and paused flags) also happens on Ctrl-C or a stopped task.
trap 'exit 130' INT
trap 'exit 143' TERM

# Airflow 3 REST API: exchange the chart's default user for a JWT, then call /api/v2.
TOKEN=""
api() { # method path [json-body]; on an HTTP error the response body goes to stderr
  local out
  out=$(curl -sS --fail-with-body -X "$1" -H "Authorization: Bearer $TOKEN" \
    -H 'Content-Type: application/json' ${3:+-d "$3"} "$API$2") || {
    echo "API $1 $2 failed: $out" >&2
    return 1
  }
  printf '%s\n' "$out"
}
refresh_token() {
  TOKEN=$(curl -sf -X POST -H 'Content-Type: application/json' \
    -d '{"username":"admin","password":"admin"}' "$API/auth/token" | jq -r .access_token) ||
    fail "could not get an API token"
}

# Wait until the dag-processor has parsed DAG $1 from the DAG folder. A DAG whose file disappeared
# still answers GET /dags/<id> but with is_stale=true, and triggering it returns 404.
wait_dag_ready() { # dag_id [timeout-seconds]
  local end=$((SECONDS + ${2:-120})) stale=""
  while [ $SECONDS -lt $end ]; do
    stale=$(api GET "/api/v2/dags/$1" 2>/dev/null | jq -r .is_stale) || stale=""
    [ "$stale" = false ] && return 0
    sleep 2
  done
  fail "DAG $1 is not parsed (is_stale=${stale:-unknown}); is airflow/dags mounted on the workers? see platform/kind/ensure-dag-mount.sh"
}
