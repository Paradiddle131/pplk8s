#!/usr/bin/env bash
# The scored agent eval (issue #102, semantic/PLAN.md SL-5): builds the sales, returns and finance
# models on dbt/dev/fixture.sql in the Compose warehouse's dbt_dev database, writes the catalog
# (make dbt-catalog), gives the agents' read-only roles their grants there, then runs every question
# of services/semantic-agent/evals/questions.yaml through the semantic agent and the text-to-SQL
# baseline on the same model, and writes both scores to docs/research/semantic-agent-eval.md.
# Live: spends about 2 x 15 model turns of the free tier (MODEL_BACKEND, MODEL_ID; the key from
# OPENROUTER_API_KEY or the cloud network secret). Pass question ids to run only those (no report).
# Expects `make services-up`; never touches the `warehouse` database.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DB=dbt_dev
OUT=${TMPDIR:-/tmp}/pplk8s-agent-eval
fail() { echo "FAIL: $*" >&2; exit 1; }
psql_dev() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"
}

mkdir -p "$OUT"
# A key OpenRouter refuses fails every question (issue #116): check it before the build, on the
# endpoint that describes the key and spends no model request. The cloud proxy adds the key itself.
if [ "${MODEL_BACKEND:-openrouter}" = openrouter ]; then
  base=${OPENROUTER_API_BASE:-https://openrouter.ai/api/v1}
  auth=()
  [ -z "${OPENROUTER_API_KEY:-}" ] || auth=(-H "Authorization: Bearer $OPENROUTER_API_KEY")
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "${auth[@]}" "$base/key") || true
  case $code in
    200) ;;
    401 | 403) fail "OpenRouter refused the key (HTTP $code from $base/key): set OPENROUTER_API_KEY" ;;
    *) fail "OpenRouter's key check answered HTTP ${code:-none} ($base/key; 000: unreachable)" ;;
  esac
fi
psql_dev -c "select 1" >/dev/null 2>&1 || docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse createdb -U warehouse "$DB"
psql_dev <"$REPO/dbt/dev/fixture.sql" 2>&1 | grep -v NOTICE || true
(cd "$REPO/dbt" && DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" DBT_PROFILES_DIR="$REPO/dbt" \
  uvx --quiet --with-requirements requirements.txt --from dbt-core dbt build --select tag:sales tag:returns tag:finance --exclude tag:tlc) \
  >"$OUT/build.log" 2>&1 || { tail -30 "$OUT/build.log" >&2; fail "dbt build"; }
make -s -C "$REPO" dbt-catalog DBT_DBNAME="$DB" >"$OUT/catalog.log" 2>&1 || { tail -30 "$OUT/catalog.log" >&2; fail "make dbt-catalog"; }
for sql in 01-schemas.sql 02-agent-roles.sql; do
  psql_dev -c "set client_min_messages = warning" -f "/docker-entrypoint-initdb.d/$sql"
done
# The fixture's days as the DAGs would record them, so every answer states a freshness (SL-4):
# sales.silver takes the sales deadline (36 h) and is long late; returns.silver has none.
psql_dev <<'SQL'
INSERT INTO ops.readiness (product, interval_start, interval_end, run_id, status)
SELECT product, day, day + interval '1 day', 'fixture', 'ready'
FROM unnest(array['sales.silver', 'returns.silver']) AS product,
     generate_series(timestamptz '2026-10-01', '2026-10-02', interval '1 day') AS day
ON CONFLICT (product, interval_start, interval_end) DO NOTHING;
SQL
echo "ok: fixture built in $DB, catalog written, agent roles granted, readiness recorded"

cd "$REPO/services/semantic-agent"
export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics
export MODEL_RETRIES=${MODEL_RETRIES:-4}
uv run --quiet python -m semantic_agent.evaluation "$@"
