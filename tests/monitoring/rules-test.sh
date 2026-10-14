#!/usr/bin/env bash
# Unit-tests the Prometheus alert rules with promtool (D37): every PrometheusRule manifest in
# platform/monitoring/manifests is checked (`promtool check rules`), and every *.test.yaml here runs
# against them (`promtool test rules`). promtool comes from the Prometheus image kube-prometheus-stack
# deploys (D21), so the PromQL is the one the lab evaluates. Needs Docker and uv.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
PROMETHEUS_IMAGE=${PROMETHEUS_IMAGE:-quay.io/prometheus/prometheus:v3.15.0}
WORK=$(mktemp -d)
chmod 755 "$WORK" # the image runs promtool as nobody
trap 'rm -rf "$WORK"' EXIT

# A PrometheusRule's spec is a plain rule file; write one per manifest under its own name.
for manifest in "$REPO"/platform/monitoring/manifests/*-rules.yaml; do
  uv run --quiet --no-project --with pyyaml==6.0.2 python -c \
    'import sys, yaml; yaml.safe_dump(yaml.safe_load(open(sys.argv[1]))["spec"], open(sys.argv[2], "w"), sort_keys=False)' \
    "$manifest" "$WORK/$(basename "$manifest" .yaml).rules.yaml"
done
cp "$HERE"/*.test.yaml "$WORK"/

promtool() { docker run --rm -v "$WORK:/rules:ro" -w /rules --entrypoint promtool "$PROMETHEUS_IMAGE" "$@"; }
# Paths as the container sees them; the names have no spaces.
mapfile -t rules < <(cd "$WORK" && ls ./*.rules.yaml)
mapfile -t tests < <(cd "$WORK" && ls ./*.test.yaml)
promtool check rules "${rules[@]}"
promtool test rules "${tests[@]}"
