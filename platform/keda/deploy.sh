#!/usr/bin/env bash
# Deploy the KEDA operator into namespace `keda` (PLAN.md D24). Idempotent: safe to re-run.
# The Airflow chart owns the worker ScaledObject (workers.celery.keda in platform/helm/airflow).
set -euo pipefail
cd "$(dirname "$0")"

CHART_VERSION=2.21.0
HELM=(helm --kube-context kind-pplk8s)

helm repo add kedacore https://kedacore.github.io/charts --force-update >/dev/null

"${HELM[@]}" upgrade --install keda kedacore/keda --version "$CHART_VERSION" \
  --namespace keda --create-namespace -f values.yaml --wait --timeout 5m "$@" >/dev/null
echo "keda ready: chart $CHART_VERSION in namespace keda"
