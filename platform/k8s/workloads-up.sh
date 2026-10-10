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
# The chart's default admin user (platform/helm/airflow); the lab has no other API identity yet.
cat > airflow-api.secret.env <<ENV
AIRFLOW_USERNAME=${AIRFLOW_API_USERNAME:-admin}
AIRFLOW_PASSWORD=${AIRFLOW_API_PASSWORD:-admin}
ENV

kubectl --context kind-pplk8s apply -k .
kubectl --context kind-pplk8s -n workloads rollout status deployment/el-factory --timeout=120s
kubectl --context kind-pplk8s -n workloads rollout status deployment/event-adapter --timeout=120s
