#!/usr/bin/env bash
# Apply the workloads namespace: generate the warehouse Secret inputs, then `kubectl apply -k`. Idempotent.
# WAREHOUSE_PASSWORD matches compose.yaml's ${WAREHOUSE_PASSWORD:-warehouse}.
set -euo pipefail
cd "$(dirname "$0")/workloads"

pw="${WAREHOUSE_PASSWORD:-warehouse}"
# Lab defaults, never real credentials; the file is git-ignored and consumed by the Kustomize secretGenerator.
cat > warehouse.secret.env <<ENV
WAREHOUSE_DSN=postgresql://warehouse:${pw}@warehouse:5432/warehouse
DBT_HOST=warehouse
DBT_PORT=5432
DBT_USER=warehouse
DBT_PASSWORD=${pw}
DBT_DBNAME=warehouse
ENV
# The adapter's own Airflow API identity (Airflow role User, created by the Airflow deploy script).
cat > airflow-api.secret.env <<ENV
AIRFLOW_USERNAME=event-adapter
AIRFLOW_PASSWORD=$(../../helm/airflow/api-identity.sh)
ENV

adapter_secret() { kubectl --context kind-pplk8s -n workloads get secret event-adapter-airflow -o jsonpath='{.data}' 2>/dev/null || true; }
before=$(adapter_secret)
kubectl --context kind-pplk8s apply -k .
# The generated Secret keeps a fixed name, so a changed login does not roll the adapter by itself.
if [ -n "$before" ] && [ "$before" != "$(adapter_secret)" ]; then
  kubectl --context kind-pplk8s -n workloads rollout restart deployment/event-adapter
fi
kubectl --context kind-pplk8s -n workloads rollout status deployment/el-factory --timeout=120s
kubectl --context kind-pplk8s -n workloads rollout status deployment/event-adapter --timeout=120s
