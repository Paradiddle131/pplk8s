# Shared helpers for e2e checks that drive Airflow through its REST API (source this file).
# Provides: kc, fail, start_port_forward, refresh_token, api. Set CTX/NS/API_PORT before sourcing to override.
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

# Airflow 3 REST API: exchange the chart's default user for a JWT, then call /api/v2.
TOKEN=""
api() { # method path [json-body]
  curl -sf -X "$1" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
    ${3:+-d "$3"} "$API$2"
}
refresh_token() {
  TOKEN=$(curl -sf -X POST -H 'Content-Type: application/json' \
    -d '{"username":"admin","password":"admin"}' "$API/auth/token" | jq -r .access_token) ||
    fail "could not get an API token"
}
