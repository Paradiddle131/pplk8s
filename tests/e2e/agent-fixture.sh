#!/usr/bin/env bash
# The agents' fixture (semantic/PLAN.md SL-5): builds the sales, returns, finance, marketing, customer-actions, partner-outreach, recruitment and call-transcripts models and the legacy tables (the semantic bet's distractors, docs/research/semantic-bet/RULE.md) on
# dbt/dev/fixture.sql and the six weeks before it (dbt/dev/fixture_weeks.sql) in the Compose warehouse's dbt_dev database, writes the catalog (make dbt-catalog),
# gives the agents' read-only roles their grants there and records the fixture's days in ops.readiness.
# Used by agent-eval.sh and agent-deploy-check.sh. Expects `make services-up`; never touches `warehouse`.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=lib/dbt-deps.sh
source "$REPO/tests/e2e/lib/dbt-deps.sh"
dbt_deps "$REPO/dbt"
DB=${DB:-dbt_dev}
OUT=${TMPDIR:-/tmp}/pplk8s-agent-fixture
fail() { echo "FAIL: $*" >&2; exit 1; }
psql_dev() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"
}

mkdir -p "$OUT"
psql_dev -c "select 1" >/dev/null 2>&1 || docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse createdb -U warehouse "$DB"
psql_dev <"$REPO/dbt/dev/fixture.sql" 2>&1 | grep -v NOTICE || true
psql_dev <"$REPO/dbt/dev/fixture_weeks.sql"
(cd "$REPO/dbt" && DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" DBT_PROFILES_DIR="$REPO/dbt" \
  uvx --quiet --with-requirements requirements-postgres.txt --from dbt-core dbt build --select tag:sales tag:returns tag:finance tag:marketing tag:customer_actions tag:partner_outreach tag:recruitment tag:call_transcripts tag:legacy --exclude tag:tlc) \
  >"$OUT/build.log" 2>&1 || { tail -30 "$OUT/build.log" >&2; fail "dbt build"; }
make -s -C "$REPO" dbt-catalog DBT_DBNAME="$DB" >"$OUT/catalog.log" 2>&1 || { tail -30 "$OUT/catalog.log" >&2; fail "make dbt-catalog"; }
psql_dev -c "set client_min_messages = warning" -f /docker-entrypoint-initdb.d/01-schemas.sql
make -s -C "$REPO" agent-warehouse DBT_DBNAME="$DB" >"$OUT/agent-warehouse.log" 2>&1 ||
  { tail -30 "$OUT/agent-warehouse.log" >&2; fail "make agent-warehouse"; }
# The semantic bet's baseline reads the legacy tables too (docs/research/semantic-bet/RULE.md: every SQL arm has
# them in reach, #357); only here, in the fixture's database, never in agent_warehouse's grants.
psql_dev -c "GRANT USAGE ON SCHEMA legacy TO agent_sql; GRANT SELECT ON ALL TABLES IN SCHEMA legacy TO agent_sql;"
# The fixture's days as the DAGs would record them, so every answer states a freshness (SL-4):
# sales.silver, marketing.silver, customer_actions.silver, partner_outreach.silver, recruitment.silver and call_transcripts.silver take their pipelines' deadlines (36 h) and
# are long late; returns.silver has none.
psql_dev <<'SQL'
INSERT INTO ops.readiness (product, interval_start, interval_end, run_id, status)
SELECT product, day, day + interval '1 day', 'fixture', 'ready'
FROM unnest(array['sales.silver', 'returns.silver', 'marketing.silver', 'customer_actions.silver', 'partner_outreach.silver', 'recruitment.silver', 'call_transcripts.silver']) AS product,
     generate_series(timestamptz '2026-10-01', '2026-10-02', interval '1 day') AS day
ON CONFLICT (product, interval_start, interval_end) DO NOTHING;
SQL
echo "ok: fixture built in $DB, catalog written, agent roles granted, readiness recorded"
