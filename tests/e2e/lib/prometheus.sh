# Helpers for checks that read Prometheus (source after airflow-api.sh, which provides fail).
# Provides: start_prometheus, prom (instant query -> JSON result array), prom_value, prom_value_at,
# alert_state, wait_alert (firing|inactive). Set PROM_PORT before sourcing to override.
PROM_PORT=${PROM_PORT:-19090}
PROM=http://localhost:$PROM_PORT
prom_owned=""
start_prometheus() { # (re)connects; the forward is found by its command line, as in airflow-api.sh
  [ -z "$prom_owned" ] || stop_forward svc/kps-prometheus "$PROM_PORT"
  kubectl --context "$CTX" -n monitoring rollout status statefulset/prometheus-kps-prometheus --timeout=180s >/dev/null 2>&1 || true
  port_free "$PROM_PORT"
  kubectl --context "$CTX" -n monitoring port-forward svc/kps-prometheus "$PROM_PORT:9090" >/dev/null 2>&1 &
  prom_owned=1
  for _ in $(seq 90); do curl -sf -o /dev/null "$PROM/-/ready" 2>/dev/null && return; sleep 2; done
  fail "Prometheus not reachable on $PROM (is \`make observability-up\` done?)"
}
stop_prometheus() { [ -z "$prom_owned" ] || stop_forward svc/kps-prometheus "$PROM_PORT"; }

prom() { # promql -> the result array of an instant query
  local out
  # A drill can evict or restart Prometheus (a drained node); reconnect once before giving up.
  out=$(curl -sf "$PROM/api/v1/query" --data-urlencode "query=$1") || {
    start_prometheus
    out=$(curl -sf "$PROM/api/v1/query" --data-urlencode "query=$1") || fail "Prometheus query failed: $1"
  }
  jq -c '.data.result' <<<"$out"
}
prom_value() { # promql -> first sample value, or empty
  prom "$1" | jq -r '.[0].value[1] // empty'
}
prom_value_at() { # promql unix-time -> first sample value at that time, or empty
  curl -sf "$PROM/api/v1/query" --data-urlencode "query=$1" --data-urlencode "time=$2" |
    jq -r '.data.result[0].value[1] // empty'
}
alert_state() { # alertname -> firing | pending | inactive
  prom "ALERTS{alertname=\"$1\"}" | jq -r 'map(.metric.alertstate) | if index("firing") then "firing" elif index("pending") then "pending" else "inactive" end'
}
wait_alert() { # alertname firing|inactive timeout-seconds -> prints the seconds it took
  local name=$1 want=$2 end=$((SECONDS + $3)) start=$SECONDS state=""
  while [ $SECONDS -lt $end ]; do
    state=$(alert_state "$name")
    [ "$state" = "$want" ] && { echo $((SECONDS - start)); return 0; }
    sleep 5
  done
  fail "alert $name is '$state', not '$want', after $3 s"
}
