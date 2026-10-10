#!/usr/bin/env bash
# Make sure every kind worker sees the repo's airflow/dags through its bind mount (PLAN.md D10).
# After a Docker Desktop restart on WSL2, Docker can start the node containers before the WSL file
# share is ready; the mount then shows up as an empty tmpfs, the dag-processor finds no files, and
# every DAG goes stale (triggers answer 404). Restarting the node container re-resolves the bind.
# Idempotent; a no-op when the mounts are healthy.
set -euo pipefail

CLUSTER=pplk8s
MOUNT=/mnt/pplk8s/dags
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PROBE=sales_elt.py # any file that is always in airflow/dags

[ -f "$REPO/airflow/dags/$PROBE" ] || { echo "missing $REPO/airflow/dags/$PROBE" >&2; exit 1; }

broken=()
for node in $(kind get nodes --name "$CLUSTER"); do
  [[ $node == *worker* ]] || continue
  docker exec "$node" test -f "$MOUNT/$PROBE" || broken+=("$node")
done
[ ${#broken[@]} -eq 0 ] && exit 0

echo "DAG mount empty on ${broken[*]}; restarting those nodes to re-resolve the bind mount"
docker restart "${broken[@]}" >/dev/null
for node in "${broken[@]}"; do
  docker exec "$node" test -f "$MOUNT/$PROBE" || { echo "DAG mount still empty on $node" >&2; exit 1; }
done
kubectl --context "kind-$CLUSTER" wait --for=condition=Ready node "${broken[@]}" --timeout=180s >/dev/null
echo "DAG mount restored on ${broken[*]}"
