#!/usr/bin/env bash
# What it measures: what an open-source, unlicensed self-hosted Lightdash serves on the lab's dbt project:
# the health endpoint's licence and AI flags, its MCP endpoint and AI-agent API (Enterprise features, enabled
# by env vars but without LIGHTDASH_LICENSE_KEY), the deployed explore's translated MetricFlow metrics, and the
# SQL its free query API compiles for a metric query.
# How to run (from the repo root, the Compose warehouse up with `make services-up`, after
# probes/334_lightdash.sh has built its project copy):
#   bash docs/research/semantic-bet/probes/334_lightdash_server.sh [out-dir] [--keep]
# <out-dir> is 334_lightdash.sh's (default ${TMPDIR:-/tmp}/semantic-bet-334-lightdash); --keep leaves the
# containers up (http://localhost:$LIGHTDASH_PORT, lab@example.com).
# Env: LIGHTDASH_PORT (default 8080, on 127.0.0.1); DBT_DBNAME (the Compose database the deployed project
# reads, default warehouse; #363 points it at dbt_dev, the agents' fixture); LIGHTDASH_WAREHOUSE_CATALOG
# (1: column types from the warehouse); LIGHTDASH_IMAGE (default lightdash/lightdash:3.128.0, 15 GB unpacked);
# LIGHTDASH_CLI (default @lightdash/cli@3.128.0). Offline: the containers reach only each other and the
# Compose warehouse; no AI provider is called (the key is a placeholder).
# Leaves <out-dir>/token.txt (a personal access token) and <out-dir>/project.txt for probes on the server.
set -euo pipefail

OUT=${1:-${TMPDIR:-/tmp}/semantic-bet-334-lightdash}
KEEP=${2:-}
PROJECT="$OUT/dbt"
IMAGE=${LIGHTDASH_IMAGE:-lightdash/lightdash:3.128.0}
CLI=${LIGHTDASH_CLI:-@lightdash/cli@3.128.0}
PORT=${LIGHTDASH_PORT:-8080}
URL=http://localhost:$PORT
export DBT_DBNAME=${DBT_DBNAME:-warehouse}
# LIGHTDASH_WAREHOUSE_CATALOG=1 lets the deploy read column types from the warehouse (localhost:5433), so a
# date column becomes a date dimension with day/week/month intervals; without it every column is a string.
CATALOG=--skip-warehouse-catalog
[ "${LIGHTDASH_WAREHOUSE_CATALOG:-}" = 1 ] && CATALOG=
[ -f "$PROJECT/target/manifest.json" ] || { echo "run probes/334_lightdash.sh first" >&2; exit 1; }
# The Compose warehouse serves no TLS: without this the deployed project's queries fail
# ("The server does not support SSL connections"); compiling never connects, so #334 did not need it.
grep -q sslmode "$PROJECT/profiles.yml" ||
  sed -i "/dbname: .*DBT_DBNAME/a\\      sslmode: disable" "$PROJECT/profiles.yml"

down() { docker rm -f ld-relay ld ld-minio ld-db >/dev/null 2>&1 || true; docker network rm ldnet >/dev/null 2>&1 || true; }
down
[ "$KEEP" = --keep ] || trap down EXIT
docker network create ldnet >/dev/null
docker run -d --name ld-db --network ldnet -e POSTGRES_PASSWORD=ldpass pgvector/pgvector:pg15 >/dev/null
# Lightdash refuses to start without S3-compatible storage; MinIO (the image Lightdash's own compose file
# uses) serves a bucket made as a data directory.
docker run -d --name ld-minio --network ldnet -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
  --entrypoint sh coollabsio/minio:RELEASE.2025-10-15T17-29-55Z -c 'mkdir -p /data/default && exec minio server /data' >/dev/null
sleep 5
docker run -d --name ld --network ldnet -p "127.0.0.1:$PORT:8080" \
  -e PGHOST=ld-db -e PGPORT=5432 -e PGUSER=postgres -e PGPASSWORD=ldpass -e PGDATABASE=postgres \
  -e LIGHTDASH_SECRET=lab-not-secret -e SECURE_COOKIES=false -e SITE_URL="$URL" \
  -e S3_ENDPOINT=http://ld-minio:9000 -e S3_REGION=us-east-1 -e S3_BUCKET=default \
  -e S3_ACCESS_KEY=minioadmin -e S3_SECRET_KEY=minioadmin -e S3_FORCE_PATH_STYLE=true \
  -e AI_COPILOT_ENABLED=true -e MCP_ENABLED=true -e AI_DEFAULT_PROVIDER=openrouter -e OPENROUTER_API_KEY=placeholder \
  "$IMAGE" >/dev/null
# The CLI deploys the profile's warehouse address (localhost:5433) as the project's credentials:
# a relay in Lightdash's network namespace makes that address reach the Compose warehouse.
docker network connect pplk8s ld
docker run -d --name ld-relay --network container:ld alpine/socat:1.8.0.3 \
  TCP-LISTEN:5433,fork,reuseaddr TCP:pplk8s-warehouse-1:5432 >/dev/null
for _ in $(seq 1 90); do
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$URL/api/v1/health")" = 200 ] && break
  docker inspect -f '{{.State.Running}}' ld | grep -q true || { docker logs ld 2>&1 | tail -20; exit 1; }
  sleep 5
done

echo "== health"
curl -s "$URL/api/v1/health" | python3 -I -c 'import json, sys; r = json.load(sys.stdin)["results"]
print({k: r[k] for k in ("version", "license", "ai", "localDbtEnabled")})'

jar="$OUT/cookies.txt"
rm -f "$jar"
curl -s -c "$jar" -b "$jar" -X POST "$URL/api/v1/user" -H 'content-type: application/json' \
  -d '{"firstName":"Lab","lastName":"Owner","email":"lab@example.com","password":"lab-pass-12345"}' >/dev/null
curl -s -c "$jar" -b "$jar" -X PUT "$URL/api/v1/org" -H 'content-type: application/json' -d '{"name":"lab"}' >/dev/null
token=$(curl -s -b "$jar" -X POST "$URL/api/v1/user/me/personal-access-tokens" -H 'content-type: application/json' \
  -d '{"description":"probe","autoGenerated":false,"expiresAt":null}' |
  python3 -I -c 'import json, sys; print(json.load(sys.stdin)["results"]["token"])')
auth="Authorization: ApiKey $token"
# For a later probe on the same server (probes/363_lightdash_numbers.py): the token and, after deploy, the project.
printf '%s\n' "$token" >"$OUT/token.txt"

echo "== deploy"
# The manifest names each model's database: parse again for DBT_DBNAME's (about 10 s).
(cd "$PROJECT" && DBT_TARGET=dev DBT_PROFILES_DIR=. \
  uv run --quiet --no-project --with-requirements requirements-postgres.txt dbt parse --quiet)
(cd "$PROJECT" && LIGHTDASH_URL="$URL" LIGHTDASH_API_KEY="$token" DBT_TARGET=dev DBT_PROFILES_DIR=. \
  DBT_HOST=localhost DBT_PORT=5433 CI=true \
  uv run --quiet --no-project --with-requirements requirements-postgres.txt \
  npx -y -p node@24 -p "$CLI" lightdash deploy --create lab --project-dir . --profiles-dir . \
  --skip-dbt-compile $CATALOG --no-version-check --ignore-errors) >"$OUT/deploy.log" 2>&1
grep -E "Translated|Deploy completed|projectUuid" "$OUT/deploy.log"
project=$(grep -o 'projectUuid=[0-9a-f-]*' "$OUT/deploy.log" | cut -d= -f2)
printf '%s\n' "$project" >"$OUT/project.txt"

echo "== MCP and AI agents without a licence"
curl -s -b "$jar" -w ' [%{http_code}]\n' -X POST "$URL/api/v1/mcp" -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
curl -s -H "$auth" -w ' [%{http_code}]\n' "$URL/api/v1/projects/$project/aiAgents"

echo "== slv_orders: translated metrics"
curl -s -H "$auth" "$URL/api/v1/projects/$project/explores/slv_orders" | python3 -I -c 'import json, sys
for name, m in json.load(sys.stdin)["results"]["tables"]["slv_orders"]["metrics"].items():
    print(f"  {name} ({m['"'"'type'"'"']}): {m['"'"'sql'"'"']}")'

echo "== compiled SQL: revenue and average order value by status"
curl -s -H "$auth" -H 'content-type: application/json' -X POST \
  "$URL/api/v1/projects/$project/explores/slv_orders/compileQuery" \
  -d '{"exploreName":"slv_orders","dimensions":["slv_orders_status"],"metrics":["slv_orders_revenue_eur","slv_orders_average_order_value_eur"],"filters":{},"sorts":[],"limit":10,"tableCalculations":[]}' |
  python3 -I -c 'import json, sys; print(json.load(sys.stdin)["results"]["query"])'
