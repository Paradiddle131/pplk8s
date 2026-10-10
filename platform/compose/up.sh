#!/usr/bin/env bash
# Start the out-of-cluster services, create the buckets, and apply the warehouse DDL. Idempotent.
set -euo pipefail
cd "$(dirname "$0")"

docker compose up -d --wait

# fake-gcs has no healthcheck, so wait for it to answer on the host port.
for _ in $(seq 30); do curl -sf -o /dev/null http://localhost:4480/storage/v1/b && break; sleep 1; done

# Buckets: `staging` for EL Factory's staged pages, `landing` for files producers drop (events on).
# fake-gcs answers 409 when the bucket already exists.
for bucket in staging landing; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' -d "{\"name\":\"$bucket\"}" \
    'http://localhost:4480/storage/v1/b?project=pplk8s')
  case "$code" in 200|409) echo "bucket $bucket ready" ;; *) echo "bucket $bucket create failed: HTTP $code" >&2; exit 1 ;; esac
done

# warehouse-init runs only on an empty volume; re-apply it (every statement is IF NOT EXISTS) so
# objects added later, such as ops.file_loads, reach an existing warehouse too.
docker compose exec -T -e PGOPTIONS="-c client_min_messages=warning" warehouse psql -q -U warehouse -d warehouse -v ON_ERROR_STOP=1 \
  -f /docker-entrypoint-initdb.d/01-schemas.sql

# Let pods in the kind cluster reach these services by name, if the cluster is up.
../kind/join-services-network.sh
