# Helpers for checks that read Prometheus (source after airflow-api.sh, which provides fail).
# Provides: start_prometheus, prom (instant query -> JSON result array), prom_value, alert_state,
# wait_alert (firing|inactive). Set PROM_PORT before sourcing to override.
PROM_PORT=${PROM_PORT:-19090}
PROM=http://localhost:$PROM_PORT
prom_pf=""
start_prometheus() {
  [ -z "$prom_pf" ] || kill "$prom_pf" 2>/dev/null || true
  kubectl --context "$CTX" -n monitoring port-forward svc/kps-prometheus "$PROM_PORT:9090" >/dev/null 2>&1 &
  prom_pf=$!
  for _ in $(seq 30); do curl -sf -o /dev/null "$PROM/-/ready" 2>/dev/null && return; sleep 1; done
  fail "Prometheus not reachable on $PROM (is \`make observability-up\` done?)"
}
stop_prometheus() { [ -z "$prom_pf" ] || kill "$prom_pf" 2>/dev/null || true; }

prom() { # promql -> the result array of an instant query
  curl -sf "$PROM/api/v1/query" --data-urlencode "query=$1" | jq -c '.data.result' ||
    fail "Prometheus query failed: $1"
}
prom_value() { # promql -> first sample value, or empty
  prom "$1" | jq -r '.[0].value[1] // empty'
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
