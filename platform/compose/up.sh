#!/usr/bin/env bash
# Start the out-of-cluster services and create the staging bucket. Idempotent.
set -euo pipefail
cd "$(dirname "$0")"

docker compose up -d --wait

# fake-gcs has no healthcheck, so wait for it to answer on the host port.
for _ in $(seq 30); do curl -sf -o /dev/null http://localhost:4480/storage/v1/b && break; sleep 1; done

# fake-gcs answers 409 when the bucket already exists.
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  -H 'Content-Type: application/json' -d '{"name":"staging"}' \
  'http://localhost:4480/storage/v1/b?project=pplk8s')
case "$code" in 200|409) echo "bucket staging ready" ;; *) echo "bucket create failed: HTTP $code" >&2; exit 1 ;; esac
