#!/usr/bin/env bash
# Deploy the monitoring stack (PLAN.md D21): kube-prometheus-stack in namespace `monitoring`, then the
# scrape targets, Airflow alert rules and Grafana dashboards in manifests/. Idempotent: safe to re-run.
# The database exporters run in Compose (`make services-up`); Airflow's statsd-exporter comes with
# the Airflow chart (platform/helm/airflow/values.yaml).
set -euo pipefail
cd "$(dirname "$0")"

CHART_VERSION=92.3.0
KUBECTL=(kubectl --context kind-pplk8s)
HELM=(helm --kube-context kind-pplk8s)

helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update >/dev/null

"${HELM[@]}" upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --version "$CHART_VERSION" --namespace monitoring --create-namespace \
  -f values.yaml --wait --timeout 10m "$@" >/dev/null

# The Airflow ServiceMonitors live in namespace airflow, which may not exist before `make airflow-up`.
"${KUBECTL[@]}" create namespace airflow --dry-run=client -o yaml | "${KUBECTL[@]}" apply -f - >/dev/null
"${KUBECTL[@]}" apply -k manifests >/dev/null
echo "monitoring ready: kube-prometheus-stack $CHART_VERSION in namespace monitoring (make grafana-ui)"
