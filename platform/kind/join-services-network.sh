#!/usr/bin/env bash
# Attach the kind nodes to the Compose network `pplk8s`, so pods reach the
# out-of-cluster stand-ins by their Compose names (warehouse, gcs, ...).
# CoreDNS forwards non-cluster names to the node's resolver, which is Docker's
# embedded DNS; it answers for every network the node is attached to.
# fake-gcs advertises http://gcs:4443 for uploads, so this is what makes
# resumable uploads work from pods. Idempotent; a no-op until both exist.
set -euo pipefail

CLUSTER=pplk8s
NETWORK=pplk8s

docker network inspect "$NETWORK" >/dev/null 2>&1 || { echo "network $NETWORK not up yet; skipping join"; exit 0; }
kind get clusters 2>/dev/null | grep -qx "$CLUSTER" || { echo "cluster $CLUSTER not up yet; skipping join"; exit 0; }

for node in $(kind get nodes --name "$CLUSTER"); do
  if [ "$(docker inspect -f "{{json .NetworkSettings.Networks.$NETWORK}}" "$node")" = null ]; then
    docker network connect "$NETWORK" "$node"
    echo "joined $node to network $NETWORK"
  fi
done
