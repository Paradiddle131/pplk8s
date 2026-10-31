#!/usr/bin/env bash
# Make sure every kind worker sees the repo's airflow/dags through its bind mount (PLAN.md D10).
# After a Docker Desktop restart on WSL2, Docker can start the node containers before the WSL file
# share is ready; the mount then shows up as an empty tmpfs, the dag-processor finds no files, and
# every DAG goes stale (triggers answer 404). Restarting the node container re-resolves the bind.
# The mount is the airflow/dags of the clone that created the cluster (cluster-up.sh writes its path
# once), so a deploy from another clone would serve that clone's DAGs (issue #173): the workers'
# DAG files must match this checkout's, or this fails naming both.
# Idempotent; a no-op when the mounts are healthy.
set -euo pipefail

CLUSTER=pplk8s
MOUNT=/mnt/pplk8s/dags
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PROBE=sales_elt.py # any file that is always in airflow/dags
# One digest over every DAG file's name and content, the same command on the host and in a node. A path
# comparison would not do: Docker Desktop on WSL2 reports a rewritten source for a bind mount.
DIGEST='find . -name "*.py" -type f | LC_ALL=C sort | xargs sha256sum | sha256sum | cut -c1-12'

[ -f "$REPO/airflow/dags/$PROBE" ] || { echo "missing $REPO/airflow/dags/$PROBE" >&2; exit 1; }

workers=()
for node in $(kind get nodes --name "$CLUSTER"); do
  [[ $node == *worker* ]] && workers+=("$node")
done

check_source() {
  local here node there source
  here=$(cd "$REPO/airflow/dags" && sh -c "$DIGEST")
  for node in "${workers[@]}"; do
    there=$(docker exec "$node" sh -c "cd $MOUNT && $DIGEST")
    [ "$there" = "$here" ] && continue
    source=$(docker inspect "$node" --format "{{range .Mounts}}{{if eq .Destination \"$MOUNT\"}}{{.Source}}{{end}}{{end}}")
    echo "the kind workers mount another clone's DAGs: $node serves ${source:-?} (digest $there)," >&2
    echo "not this checkout's $REPO/airflow/dags (digest $here); a local DAG deploy would run those." >&2
    echo "Run make from that clone, or recreate the cluster from this one: make cluster-down cluster-up" >&2
    exit 1
  done
}

broken=()
for node in "${workers[@]}"; do
  docker exec "$node" test -f "$MOUNT/$PROBE" || broken+=("$node")
done
[ ${#broken[@]} -eq 0 ] && { check_source; exit 0; }

echo "DAG mount empty on ${broken[*]}; restarting those nodes to re-resolve the bind mount"
docker restart "${broken[@]}" >/dev/null
for node in "${broken[@]}"; do
  docker exec "$node" test -f "$MOUNT/$PROBE" || { echo "DAG mount still empty on $node" >&2; exit 1; }
done
kubectl --context "kind-$CLUSTER" wait --for=condition=Ready node "${broken[@]}" --timeout=180s >/dev/null
echo "DAG mount restored on ${broken[*]}"
check_source
