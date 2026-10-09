#!/usr/bin/env bash
# Deploy Airflow to the kind cluster with the official chart. Idempotent: safe to re-run.
# Builds and pushes the image, creates generated secrets once, applies the PV/PVC and
# RBAC, runs `helm upgrade --install`, and ensures the Phase 4 pool exists.
# Extra arguments are passed through to `helm upgrade` (e.g. --set key=value).
set -euo pipefail
cd "$(dirname "$0")"
REPO="$(cd ../../.. && pwd)"

CHART_VERSION=1.22.0
RELEASE=airflow
NAMESPACE=airflow
AIRFLOW_IMAGE="${AIRFLOW_IMAGE:?set AIRFLOW_IMAGE (make airflow-up does)}"
METADATA_DB_PASSWORD="${METADATA_DB_PASSWORD:-airflow}"
KUBECTL=(kubectl --context kind-pplk8s)
HELM=(helm --kube-context kind-pplk8s)

helm repo add apache-airflow https://airflow.apache.org --force-update >/dev/null

# Image: build from airflow/ (context excludes dags/tests) and push to the local registry.
docker build -t "$AIRFLOW_IMAGE" "$REPO/airflow"
docker push "$AIRFLOW_IMAGE" >/dev/null

# The metadata DB lives in Compose; make sure it is up and the nodes can resolve it (D13).
docker compose -f "$REPO/platform/compose/compose.yaml" up -d --wait metadata-db
"$REPO/platform/kind/join-services-network.sh"

"${KUBECTL[@]}" apply -f manifests.yaml >/dev/null

# Generated secrets are created once and never rotated by a re-run: a new fernet key would make
# stored connections unreadable, a new JWT secret would break running tasks.
ensure_secret() { # name key generator-command...
  local name=$1 key=$2
  shift 2
  if ! "${KUBECTL[@]}" -n "$NAMESPACE" get secret "$name" >/dev/null 2>&1; then
    "${KUBECTL[@]}" -n "$NAMESPACE" create secret generic "$name" --from-literal="$key=$("$@")" >/dev/null
    echo "created secret $name"
  fi
}
ensure_secret airflow-fernet-key fernet-key python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())'
ensure_secret airflow-api-secret api-secret-key openssl rand -hex 32
ensure_secret airflow-jwt-secret jwt-secret openssl rand -hex 32

# Rendered from env on every run (cheap, and keeps the password in step with Compose).
# With PgBouncer on, Airflow connects to the PgBouncer service, whose database alias is
# <release>-metadata; PgBouncer in turn connects to metadata-db (data.metadataConnection).
"${KUBECTL[@]}" -n "$NAMESPACE" create secret generic airflow-metadata \
  --from-literal="connection=postgresql://airflow:${METADATA_DB_PASSWORD}@${RELEASE}-pgbouncer.${NAMESPACE}:6543/${RELEASE}-metadata?sslmode=disable" \
  --dry-run=client -o yaml | "${KUBECTL[@]}" apply -f - >/dev/null

# Connections for Phase 4, as AIRFLOW_CONN_* env vars (URI form; the conn_id is the suffix).
"${KUBECTL[@]}" -n "$NAMESPACE" create secret generic airflow-connections \
  --from-literal='AIRFLOW_CONN_EL_FACTORY=http://el-factory.workloads.svc.cluster.local:80' \
  --from-literal='AIRFLOW_CONN_WAREHOUSE=postgresql://warehouse:warehouse@warehouse:5432/warehouse' \
  --dry-run=client -o yaml | "${KUBECTL[@]}" apply -f - >/dev/null

# The chart's one-shot Jobs are plain resources here (values.yaml) and immutable: clear finished
# ones so an upgrade can recreate them. Their pods are what `airflow db migrate` runs in.
"${KUBECTL[@]}" -n "$NAMESPACE" delete job --ignore-not-found --wait=true \
  "$RELEASE-run-airflow-migrations" "$RELEASE-create-user" >/dev/null

# --wait-for-jobs makes Helm wait for the migration and user-creation Jobs too.
"${HELM[@]}" upgrade --install "$RELEASE" apache-airflow/airflow \
  --version "$CHART_VERSION" --namespace "$NAMESPACE" \
  -f values.yaml \
  --set "images.airflow.repository=${AIRFLOW_IMAGE%:*}" \
  --set "images.airflow.tag=${AIRFLOW_IMAGE##*:}" \
  --set "data.metadataConnection.pass=${METADATA_DB_PASSWORD}" \
  --wait --wait-for-jobs --timeout 10m "$@" >/dev/null

# Pool for Phase 4 extraction concurrency; `pools set` creates or updates.
"${KUBECTL[@]}" -n "$NAMESPACE" exec deploy/airflow-scheduler -c scheduler -- \
  airflow pools set el_factory 7 "EL Factory concurrency" >/dev/null
echo "airflow ready: release $RELEASE (chart $CHART_VERSION), pool el_factory=7"
