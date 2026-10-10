# Shared helpers for e2e checks that drive Airflow through its REST API (source this file).
# Provides: kc, fail, start_port_forward, refresh_token, api, wait_dag_ready, worker_pod, run_hello. Set CTX/NS/API_PORT before sourcing to override.
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

# Map a task instance's hostname to the Celery worker pod that ran it, or fail. Workers report their
# pod IP (a Deployment's pod names do not resolve, and the api-server fetches live logs by hostname),
# while older runs carry a StatefulSet pod FQDN (airflow-worker-N.airflow-worker...).
worker_pod() { # hostname -> pod name
  local pod
  case "$1" in
    airflow-worker-*) pod=${1%%.*} ;;
    *) pod=$(kc get pod -l component=worker --field-selector "status.podIP=$1" -o name | head -1) ;;
  esac
  [ -n "$pod" ] || fail "host '$1' is not a Celery worker pod"
  echo "${pod#pod/}"
}

# Trigger the hello DAG and wait for it to succeed; prints the worker pod that ran the task.
run_hello() {
  local run_id state host
  start_port_forward
  refresh_token
  # The dag-processor parses the DAG folder periodically; wait until hello is known.
  wait_dag_ready hello
  api PATCH /api/v2/dags/hello '{"is_paused":false}' >/dev/null
  run_id=$(api POST /api/v2/dags/hello/dagRuns '{"logical_date":null}' | jq -r .dag_run_id)
  [ -n "$run_id" ] && [ "$run_id" != null ] || fail "could not trigger hello"
  for _ in $(seq 90); do
    state=$(api GET "/api/v2/dags/hello/dagRuns/$run_id" | jq -r .state)
    case "$state" in success) break ;; failed) fail "hello run $run_id failed" ;; esac
    sleep 2
  done
  [ "$state" = success ] || fail "hello run $run_id still $state after 180 s"
  host=$(api GET "/api/v2/dags/hello/dagRuns/$run_id/taskInstances/say_hello" | jq -r .hostname)
  worker_pod "$host"
}
