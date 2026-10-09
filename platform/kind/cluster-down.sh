#!/usr/bin/env bash
# Delete the kind cluster and the local registry container. Safe to re-run.
set -euo pipefail

kind delete cluster --name pplk8s
docker rm -f kind-registry >/dev/null 2>&1 && echo "removed registry kind-registry" || true
