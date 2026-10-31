# Shared helpers for e2e checks that drive Airflow through its REST API (source this file).
# Provides: kc, fail, start_port_forward, ensure_port_forward, refresh_token, api, wait_dag_ready,
# discard_scheduled_runs, worker_pod, run_hello, require_synced_dags. Set CTX/NS/API_PORT before sourcing to override.
CTX=${CTX:-kind-pplk8s}
NS=${NS:-airflow}
API_PORT=${API_PORT:-18080}
API=http://localhost:$API_PORT
kc() { kubectl --context "$CTX" -n "$NS" "$@"; }
fail() { echo "FAIL: $*" >&2; exit 1; }

# A port-forward is bound to one api-server pod, so it is restarted after each rollout. Checks call
# these helpers from command substitutions (subshells) too, so the forward is found by its command
# line, not by a PID only one shell knows, and ownership is a flag file keyed by $$, which every
# subshell of a check shares: a subshell that started or restarted the forward used to leave its
# kubectl running after the check, and the LEDGER's leaked port-forwards came from that and from
# backgrounding the kc function (whose PID is a subshell, not kubectl).
pf_owned="${TMPDIR:-/tmp}/pplk8s-port-forward.$$"
dags_checked=""
start_port_forward() {
  # Every check starts here, so this is where it proves it tests the DAG code it was written for.
  [ -n "$dags_checked" ] || { require_synced_dags; dags_checked=1; }
  [ ! -e "$pf_owned" ] || stop_forward svc/airflow-api-server "$API_PORT"
  # A port-forward leaked by another shell must not stand in for ours: it may be bound to a pod a
  # rollout already replaced.
  port_free "$API_PORT"
  kubectl --context "$CTX" -n "$NS" port-forward svc/airflow-api-server "$API_PORT:8080" >/dev/null 2>&1 &
  touch "$pf_owned"
  for _ in $(seq 30); do curl -sf -o /dev/null "$API/api/v2/version" 2>/dev/null && return; sleep 1; done
  fail "API not reachable on $API"
}
ensure_port_forward() { # keeps a forward of ours that still answers, else (re)starts one
  [ -e "$pf_owned" ] && curl -sf -m 5 -o /dev/null "$API/api/v2/version" 2>/dev/null && return
  start_port_forward
}
stop_forward() { # svc/<name> local-port -> kills that kubectl port-forward and waits for the port
  pkill -f "^kubectl .*port-forward $1 $2:" 2>/dev/null
  for _ in $(seq 20); do listening "$2" || return 0; sleep 0.5; done
}
listening() { # port -> succeeds when a TCP socket listens on it (ss where installed, else /proc/net/tcp*)
  if command -v ss >/dev/null; then
    [ -n "$(ss -Hltn "sport = :$1")" ]
  else # state 0A is LISTEN; the local port is hex after the colon
    local tables=(/proc/net/tcp)
    [ -r /proc/net/tcp6 ] && tables+=(/proc/net/tcp6)
    awk -v p="$(printf '%04X' "$1")" 'FNR > 1 && $4 == "0A" && substr($2, length($2) - 3) == p { found = 1 } END { exit !found }' "${tables[@]}"
  fi
}
port_free() { # port -> fails when something already listens on it
  # A socket table, not a test connection: on WSL2 a connect to a closed localhost port can hang instead of failing.
  if listening "$1"; then
    fail "port $1 is already in use, e.g. by a leaked port-forward: $(pgrep -fa "^kubectl .*port-forward.* $1:" || echo unknown)"
  fi
}
stop_port_forward() {
  [ -e "$pf_owned" ] || return 0
  stop_forward svc/airflow-api-server "$API_PORT"
  rm -f "$pf_owned"
}
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

# Unpausing a scheduled DAG makes the scheduler create its latest scheduled run (catchup=False still
# creates one), which a check never asked for: finance_daily's then defers for 6 h on an interval
# whose producers never land, fails, and fires a late alert. A check's exit trap discards those
# runs: fail first (that ends deferred or running tasks and releases their triggers), then delete.
discard_scheduled_runs() { # dag_id since(UTC, %Y-%m-%dT%H:%M:%SZ) -> discards runs queued since then
  local id path
  for id in $(api GET "/api/v2/dags/$1/dagRuns?run_type=scheduled&limit=100&order_by=-run_after" |
    jq -r --arg s "$2" '.dag_runs[] | select((.queued_at // "" | sub("\\.[0-9]+"; "")) >= $s) | .dag_run_id'); do
    path="/api/v2/dags/$1/dagRuns/$(jq -rn --arg i "$id" '$i|@uri')"
    api PATCH "$path" '{"state":"failed"}' >/dev/null
    api DELETE "$path" >/dev/null && echo "discarded the scheduled run $1/$id"
  done
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
  ensure_port_forward
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

# With git-sync (PLAN.md D23) the cluster runs the airflow/ tree of the commit it synced from main,
# not this checkout's. A check that asserts on DAG behaviour must test the code it was written
# against, so refuse to run when the local airflow/ differs from that commit (uncommitted or
# unpushed edits, or a stale sync). A no-op with the host-path overlay, where the checkout is live.
require_synced_dags() {
  local repo served
  repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
  kc get deploy airflow-dag-processor -o jsonpath='{.spec.template.spec.containers[*].name}' |
    grep -qw git-sync || return 0
  served=$(kc exec deploy/airflow-dag-processor -c dag-processor -- readlink /opt/airflow/dags/repo) ||
    fail "cannot read the commit git-sync serves"
  served=${served##*/}
  git -C "$repo" cat-file -e "$served^{commit}" 2>/dev/null || git -C "$repo" fetch -q origin
  git -C "$repo" cat-file -e "$served^{commit}" 2>/dev/null ||
    fail "git-sync serves $served, which this checkout does not know"
  if ! git -C "$repo" diff --quiet "$served" -- airflow/ ||
    [ -n "$(git -C "$repo" ls-files --others --exclude-standard -- airflow/)" ]; then
    fail "local airflow/ differs from the commit git-sync serves (${served:0:8}); push and merge to main, wait for the sync, or deploy with DAG_DELIVERY=local"
  fi
  echo "dags: git-sync serves ${served:0:8}, matching the local airflow/" >&2
}
