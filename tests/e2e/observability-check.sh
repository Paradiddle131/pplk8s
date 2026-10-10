#!/usr/bin/env bash
# Observability check (PLAN.md D21): after a task has run, every series the "Airflow overview"
# dashboard plots is present in Prometheus with the labels the panels group by, the Airflow alert
# rules are loaded, and Grafana lists the dashboard. Expects `make airflow-up observability-up`.
set -euo pipefail

source "$(dirname "$0")/lib/airflow-api.sh"
source "$(dirname "$0")/lib/prometheus.sh"
trap 'stop_prometheus; stop_port_forward' EXIT

pod=$(run_hello)
echo "ok: hello ran on $pod"
start_prometheus

# Each entry: a series the dashboard needs, and the label its panels group by ("-" for none).
series=(
  "airflow_scheduler_heartbeat -"
  "airflow_dag_processor_heartbeat -"
  "airflow_triggerer_heartbeat -"
  "airflow_executor_queued_tasks executor_class_name"
  "airflow_executor_running_tasks executor_class_name"
  "airflow_executor_open_slots executor_class_name"
  "airflow_pool_open_slots pool_name"
  "airflow_pool_running_slots pool_name"
  "airflow_pool_queued_slots pool_name"
  "airflow_pool_starving_tasks pool_name"
  "airflow_task_duration_seconds_bucket dag_id"
  "airflow_ti_successes -"
  "airflow_dag_processing_import_errors -"
  "airflow_triggers_running hostname"
  "pg_up database"
  "pgbouncer_exporter_pools_waiting_clients -"
  "kube_deployment_status_replicas_available deployment"
  "container_memory_working_set_bytes pod"
)
# The exporter drops counters idle for 5 minutes (histograms after 1 hour), so a series hello just
# re-created reaches Prometheus only on the next scrape; poll each one instead of one sentinel.
for entry in "${series[@]}"; do
  read -r name label <<<"$entry"
  for _ in $(seq 12); do
    result=$(prom "$name")
    [ "$(jq length <<<"$result")" -gt 0 ] && break
    sleep 5
  done
  [ "$(jq length <<<"$result")" -gt 0 ] || fail "no series for $name"
  if [ "$label" != - ]; then
    jq -e --arg l "$label" 'any(.[]; .metric[$l] != null and .metric[$l] != "")' <<<"$result" >/dev/null ||
      fail "$name has no '$label' label"
  fi
done
echo "ok: ${#series[@]} dashboard series present with their labels"
[ "$(prom 'airflow_pool_open_slots{pool_name="el_factory"}' | jq length)" = 1 ] ||
  fail "pool el_factory is not its own series (are InfluxDB-style statsd tags on?)"
echo "ok: pools are separate series (el_factory open slots: $(prom_value 'airflow_pool_open_slots{pool_name="el_factory"}'))"

rules=$(curl -sf "$PROM/api/v1/rules?type=alert" | jq '[.data.groups[] | select(.name|startswith("airflow.")) | .rules[]] | length')
[ "$rules" -ge 10 ] || fail "only $rules Airflow alert rules loaded"
firing=$(prom 'ALERTS{alertstate="firing", alertname=~"Airflow.*|MetadataDB.*|KubeNode.*"}' | jq -r 'map(.metric.alertname) | join(",")')
[ -z "$firing" ] || fail "alerts firing on a healthy lab: $firing"
echo "ok: $rules Airflow alert rules loaded, none firing"

kubectl --context "$CTX" -n monitoring port-forward svc/grafana 13000:80 >/dev/null 2>&1 &
gpf=$!
trap 'kill $gpf 2>/dev/null; stop_prometheus; stop_port_forward' EXIT
for _ in $(seq 30); do curl -sf -o /dev/null http://localhost:13000/api/health && break; sleep 1; done
title=$(curl -sf -u admin:admin 'http://localhost:13000/api/search?query=Airflow%20overview' | jq -r '.[0].title // empty')
[ "$title" = "Airflow overview" ] || fail "Grafana does not list the Airflow overview dashboard"
echo "ok: Grafana lists '$title'"
echo "observability-check passed"
