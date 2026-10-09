#!/usr/bin/env bash
# Phase 0 exit check: the cluster has a control plane and two Ready workers,
# and an image pushed to localhost:5001 from the host runs as a pod in-cluster.
set -euo pipefail

CTX=kind-pplk8s
IMAGE=localhost:5001/registry-probe:latest

ready_workers=$(kubectl --context "$CTX" get nodes -l '!node-role.kubernetes.io/control-plane' \
  -o jsonpath='{range .items[*]}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' | grep -c True || true)
[ "$ready_workers" -ge 2 ] || { echo "FAIL: expected >=2 Ready workers, got $ready_workers" >&2; exit 1; }
echo "ok: $ready_workers Ready workers"

docker pull -q busybox:1.37 >/dev/null
docker tag busybox:1.37 "$IMAGE"
docker push -q "$IMAGE" >/dev/null
echo "ok: pushed $IMAGE from the host"

kubectl --context "$CTX" delete pod registry-probe --ignore-not-found >/dev/null
kubectl --context "$CTX" run registry-probe --image "$IMAGE" --restart Never \
  --image-pull-policy Always -- echo pulled-from-local-registry >/dev/null
kubectl --context "$CTX" wait pod/registry-probe --for jsonpath='{.status.phase}'=Succeeded --timeout 90s >/dev/null
out=$(kubectl --context "$CTX" logs registry-probe)
kubectl --context "$CTX" delete pod registry-probe >/dev/null
[ "$out" = pulled-from-local-registry ] || { echo "FAIL: unexpected pod output: $out" >&2; exit 1; }
echo "ok: pod pulled $IMAGE inside the cluster"
