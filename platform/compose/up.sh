#!/usr/bin/env bash
# Start the out-of-cluster services, create the buckets, and apply the warehouse DDL. Idempotent.
set -euo pipefail
cd "$(dirname "$0")"

# The project name is fixed, so `up` from a linked git worktree recreates the lab's containers with
# their bind mounts (./sql-exporter, ./warehouse-init) inside that worktree; once it is removed,
# they mount nothing on their next restart. Say so, so the main checkout takes them back.
git_dir=$(git rev-parse --path-format=absolute --git-dir 2>/dev/null || true)
if [ -n "$git_dir" ] && [ "$git_dir" != "$(git rev-parse --path-format=absolute --git-common-dir)" ]; then
  echo "warning: services now bind-mount files from this worktree ($PWD)." >&2
  echo "warning: run 'make services-up' from the main checkout before removing it." >&2
fi

docker compose up -d --wait

# sql_exporter reads its config and collectors only at start, and `up` does not recreate a container
# when a bind-mounted file changes (a branch switch that adds a collector), so restart an exporter
# whose config is newer than its process.
for svc in metadata-db-sql-exporter warehouse-sql-exporter; do
  started=$(docker inspect -f '{{.State.StartedAt}}' "$(docker compose ps -q "$svc")")
  if [ -n "$(find sql-exporter -newermt "$started" -print -quit)" ]; then
    docker compose restart "$svc" >/dev/null
    echo "$svc restarted: its config changed since it started"
  fi
done

# fake-gcs has no healthcheck, so wait for it to answer on the host port.
for _ in $(seq 30); do curl -sf -o /dev/null http://localhost:4480/storage/v1/b && break; sleep 1; done

# Buckets: `staging` for EL Factory's staged pages, `landing` for files producers drop (events on),
# `airflow-logs` for Airflow's remote task logs (PLAN.md D22). fake-gcs answers 409 when it exists.
for bucket in staging landing airflow-logs; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
    -H 'Content-Type: application/json' -d "{\"name\":\"$bucket\"}" \
    'http://localhost:4480/storage/v1/b?project=pplk8s')
  case "$code" in 200|409) echo "bucket $bucket ready" ;; *) echo "bucket $bucket create failed: HTTP $code" >&2; exit 1 ;; esac
done

# warehouse-init runs only on an empty volume; re-apply it (every statement is IF NOT EXISTS) so
# objects added later, such as ops.file_loads, reach an existing warehouse too.
docker compose exec -T -e PGOPTIONS="-c client_min_messages=warning" warehouse psql -q -U warehouse -d warehouse -v ON_ERROR_STOP=1 \
  -f /docker-entrypoint-initdb.d/01-schemas.sql
# The semantic agent's roles, grants and audit table come from the dbt project, so they land wherever it
# builds (dbt/macros/agent_warehouse.sql, semantic/PLAN.md SL-10); after 01, whose ledger they grant.
make -s -C ../.. agent-warehouse DBT_DBNAME=warehouse >/dev/null
echo "warehouse: the semantic agent's roles and audit table ready"

# The semantic agent's ADK sessions (semantic/PLAN.md SL-2): their own database and owner on the
# metadata DB's instance, as a second database on the same Cloud SQL instance would be.
docker compose exec -T metadata-db psql -q -U airflow -d airflow -v ON_ERROR_STOP=1 <<'SQL'
SELECT 'CREATE ROLE agent_sessions LOGIN PASSWORD ''agent_sessions'''
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'agent_sessions')\gexec
SELECT 'CREATE DATABASE agent_sessions OWNER agent_sessions'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'agent_sessions')\gexec
SQL

# Let pods in the kind cluster reach these services by name, if the cluster is up.
../kind/join-services-network.sh
