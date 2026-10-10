#!/usr/bin/env bash
# Print the event adapter's Airflow API password, generating it once into Secret
# airflow/airflow-api-event-adapter (keys username, password). Each REST caller gets its own
# identity instead of the chart's admin login; deploy.sh turns this Secret into an Airflow user
# and workloads-up.sh hands the same credentials to the adapter. Never rotated by a re-run.
set -euo pipefail
KUBECTL=(kubectl --context kind-pplk8s)
NAME=airflow-api-event-adapter
USERNAME=event-adapter

"${KUBECTL[@]}" create namespace airflow --dry-run=client -o yaml | "${KUBECTL[@]}" apply -f - >/dev/null
if ! "${KUBECTL[@]}" -n airflow get secret "$NAME" >/dev/null 2>&1; then
  "${KUBECTL[@]}" -n airflow create secret generic "$NAME" \
    --from-literal="username=$USERNAME" --from-literal="password=$(openssl rand -hex 16)" >/dev/null
  echo "created secret $NAME" >&2
fi
"${KUBECTL[@]}" -n airflow get secret "$NAME" -o jsonpath='{.data.password}' | base64 -d
