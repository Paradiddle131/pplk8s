#!/usr/bin/env bash
# Deploy the KEDA operator into namespace `keda` (PLAN.md D24). Idempotent: safe to re-run.
# The Airflow chart owns the worker ScaledObject (workers.celery.keda in platform/helm/airflow).
set -euo pipefail
cd "$(dirname "$0")"

CHART_VERSION=2.21.0
KUBECTL=(kubectl --context kind-pplk8s)
HELM=(helm --kube-context kind-pplk8s)

helm repo add kedacore https://kedacore.github.io/charts --force-update >/dev/null

monitor=()
if "${KUBECTL[@]}" get crd servicemonitors.monitoring.coreos.com >/dev/null 2>&1; then
  monitor=(--set prometheus.operator.serviceMonitor.enabled=true)
fi
"${HELM[@]}" upgrade --install keda kedacore/keda --version "$CHART_VERSION" \
  --namespace keda --create-namespace -f values.yaml "${monitor[@]}" --wait --timeout 5m "$@" >/dev/null
echo "keda ready: chart $CHART_VERSION in namespace keda"
