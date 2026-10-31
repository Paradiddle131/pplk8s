#!/usr/bin/env bash
# Delete the kind cluster, the local registry container and the egress relay (if any). Safe to re-run.
set -euo pipefail

kind delete cluster --name pplk8s
docker rm -f kind-registry >/dev/null 2>&1 && echo "removed registry kind-registry" || true
docker rm -f kind-egress >/dev/null 2>&1 && echo "removed relay kind-egress" || true
