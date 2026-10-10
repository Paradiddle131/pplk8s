#!/usr/bin/env bash
# Deploy Airflow to the kind cluster with the official chart. Idempotent: safe to re-run.
# Builds and pushes the image, creates generated secrets once, applies the PV/PVC and
# RBAC, runs `helm upgrade --install`, and ensures the Phase 4 pool exists.
# Extra arguments are passed through to `helm upgrade` (e.g. --set key=value or -f <overlay>).
# DAG_DELIVERY=git-sync (default, D23) syncs `main` from GitHub with the deploy key in
# GIT_SYNC_SSH_KEY; DAG_DELIVERY=local mounts this checkout's airflow/dags instead (dev loop, CI).
set -euo pipefail
cd "$(dirname "$0")"
REPO="$(cd ../../.. && pwd)"

# The upgrade drill (tests/e2e/phase6-upgrade-drill.sh) deploys an older chart and a prebuilt image
# with CHART_VERSION and AIRFLOW_IMAGE_BUILD=0; everything else always uses these defaults.
CHART_VERSION="${CHART_VERSION:-1.22.0}"
RELEASE=airflow
NAMESPACE=airflow
AIRFLOW_IMAGE="${AIRFLOW_IMAGE:?set AIRFLOW_IMAGE (make airflow-up does)}"
METADATA_DB_PASSWORD="${METADATA_DB_PASSWORD:-airflow}"
WAREHOUSE_PASSWORD="${WAREHOUSE_PASSWORD:-warehouse}" # same default as compose.yaml and workloads-up.sh
DAG_DELIVERY="${DAG_DELIVERY:-git-sync}"
GIT_SYNC_SSH_KEY="${GIT_SYNC_SSH_KEY:-$HOME/.ssh/pplk8s-deploy}"
KUBECTL=(kubectl --context kind-pplk8s)
HELM=(helm --kube-context kind-pplk8s)

helm repo add apache-airflow https://airflow.apache.org --force-update >/dev/null

# Image: build from airflow/ (context excludes dags/tests) and push to the local registry.
if [ "${AIRFLOW_IMAGE_BUILD:-1}" = 1 ]; then
  docker build -t "$AIRFLOW_IMAGE" "$REPO/airflow"
fi
docker push "$AIRFLOW_IMAGE" >/dev/null

# The metadata DB lives in Compose; make sure it is up and the nodes can resolve it (D13).
docker compose -f "$REPO/platform/compose/compose.yaml" up -d --wait metadata-db
"$REPO/platform/kind/join-services-network.sh"

"${KUBECTL[@]}" apply -f manifests.yaml >/dev/null

overlays=()
case "$DAG_DELIVERY" in
  local)
    "$REPO/platform/kind/ensure-dag-mount.sh"
    "${KUBECTL[@]}" apply -f dags-hostpath.yaml >/dev/null
    overlays=(-f values-local-dags.yaml)
    ;;
  git-sync)
    # The read-only deploy key stays outside the repo; the Secret is created once from it.
    if ! "${KUBECTL[@]}" -n "$NAMESPACE" get secret airflow-git-ssh >/dev/null 2>&1; then
      [ -r "$GIT_SYNC_SSH_KEY" ] || {
        echo "git-sync needs a read-only deploy key at $GIT_SYNC_SSH_KEY (PLAN.md D23):" >&2
        echo "  ssh-keygen -t ed25519 -N '' -f $GIT_SYNC_SSH_KEY" >&2
        echo "  gh repo deploy-key add $GIT_SYNC_SSH_KEY.pub --title pplk8s-git-sync" >&2
        echo "or deploy with DAG_DELIVERY=local." >&2
        exit 1
      }
      "${KUBECTL[@]}" -n "$NAMESPACE" create secret generic airflow-git-ssh \
        --from-file="gitSshKey=$GIT_SYNC_SSH_KEY" >/dev/null
      echo "created secret airflow-git-ssh"
    fi
    ;;
  *) echo "DAG_DELIVERY must be git-sync or local, not '$DAG_DELIVERY'" >&2; exit 1 ;;
esac

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

# Connections as AIRFLOW_CONN_* env vars (URI or JSON form; the conn_id is the suffix).
# pubsub_emulator (the AssetWatcher spike, D17) and gcs_logs (remote task logs, D22) use anonymous
# credentials, because the emulators ignore them and the pods have no Google credentials to find.
"${KUBECTL[@]}" -n "$NAMESPACE" create secret generic airflow-connections \
  --from-literal='AIRFLOW_CONN_EL_FACTORY=http://el-factory.workloads.svc.cluster.local:80' \
  --from-literal="AIRFLOW_CONN_WAREHOUSE=postgresql://warehouse:${WAREHOUSE_PASSWORD}@warehouse:5432/warehouse" \
  --from-literal='AIRFLOW_CONN_PUBSUB_EMULATOR={"conn_type": "google_cloud_platform", "extra": {"project": "pplk8s", "is_anonymous": true}}' \
  --from-literal='AIRFLOW_CONN_GCS_LOGS={"conn_type": "google_cloud_platform", "extra": {"project": "pplk8s", "is_anonymous": true}}' \
  --dry-run=client -o yaml | "${KUBECTL[@]}" apply -f - >/dev/null

# The chart's one-shot Jobs are plain resources here (values.yaml) and immutable: clear finished
# ones so an upgrade can recreate them. Their pods are what `airflow db migrate` runs in.
"${KUBECTL[@]}" -n "$NAMESPACE" delete job --ignore-not-found --wait=true \
  "$RELEASE-run-airflow-migrations" "$RELEASE-create-user" >/dev/null

# The chart rolls the statsd-exporter on a mapping change only for statsd.extraMappings, not for
# the overrideMappings used here; remember the ConfigMap's version to restart it ourselves.
statsd_cm() { "${KUBECTL[@]}" -n "$NAMESPACE" get cm "$RELEASE-statsd" -o jsonpath='{.metadata.resourceVersion}' 2>/dev/null || true; }
statsd_before=$(statsd_cm)

# --wait-for-jobs makes Helm wait for the migration and user-creation Jobs too.
"${HELM[@]}" upgrade --install "$RELEASE" apache-airflow/airflow \
  --version "$CHART_VERSION" --namespace "$NAMESPACE" \
  -f values.yaml "${overlays[@]}" \
  --set "images.airflow.repository=${AIRFLOW_IMAGE%:*}" \
  --set "images.airflow.tag=${AIRFLOW_IMAGE##*:}" \
  --set "data.metadataConnection.pass=${METADATA_DB_PASSWORD}" \
  --wait --wait-for-jobs --timeout 10m "$@" >/dev/null

if [ -n "$statsd_before" ] && [ "$statsd_before" != "$(statsd_cm)" ]; then
  "${KUBECTL[@]}" -n "$NAMESPACE" rollout restart deploy/"$RELEASE-statsd" >/dev/null
  "${KUBECTL[@]}" -n "$NAMESPACE" rollout status deploy/"$RELEASE-statsd" --timeout=120s >/dev/null
  echo "restarted $RELEASE-statsd for its new mappings"
fi

# With git-sync nothing uses the host-path DAG volume any more; drop it if an earlier deploy made it.
if [ "$DAG_DELIVERY" = git-sync ]; then
  "${KUBECTL[@]}" delete -f dags-hostpath.yaml --ignore-not-found --wait=false >/dev/null
fi

# Workers keep no log volume since D22 (logs go to gs://airflow-logs); a StatefulSet from an earlier
# deploy left its per-pod log PVCs behind, which nothing deletes on its own.
if ! "${KUBECTL[@]}" -n "$NAMESPACE" get statefulset "$RELEASE-worker" >/dev/null 2>&1; then
  "${KUBECTL[@]}" -n "$NAMESPACE" delete pvc -l "tier=airflow,component=worker,release=$RELEASE" \
    --ignore-not-found >/dev/null
fi

# Pools: el_factory caps extraction concurrency (Phase 4); ops_load holds the KEDA load fixture
# (ops_load_test, D24) and is the pool the slot-starvation drill shrinks. `pools set` creates or updates.
"${KUBECTL[@]}" -n "$NAMESPACE" exec deploy/airflow-scheduler -c scheduler -- \
  airflow pools set el_factory 7 "EL Factory concurrency" >/dev/null
"${KUBECTL[@]}" -n "$NAMESPACE" exec deploy/airflow-scheduler -c scheduler -- \
  airflow pools set ops_load 16 "KEDA load fixture (ops_load_test)" >/dev/null
# The event adapter's own API identity (role User: it may trigger runs, nothing more); the password
# comes from the Secret api-identity.sh generates once, so a re-run never changes it.
adapter_password=$("$PWD/api-identity.sh")
if ! "${KUBECTL[@]}" -n "$NAMESPACE" exec deploy/airflow-scheduler -c scheduler -- \
  airflow users list -o plain 2>/dev/null | grep -qw event-adapter; then
  "${KUBECTL[@]}" -n "$NAMESPACE" exec deploy/airflow-scheduler -c scheduler -- \
    airflow users create --username event-adapter --role User --password "$adapter_password" \
    --email event-adapter@example.com --firstname event --lastname adapter >/dev/null
  echo "created Airflow user event-adapter"
fi
echo "airflow ready: release $RELEASE (chart $CHART_VERSION), pools el_factory=7 ops_load=16"
