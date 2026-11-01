#!/usr/bin/env bash
# The semantic agent with only the dbt project and a warehouse (issue #166): no Airflow, no readiness
# ledger, no Compose init scripts, no session store. On a new, empty database of the Compose Postgres
# (used as a plain Postgres server) it
#   - creates the agent's roles, grants and audit table with `make agent-warehouse` (the dbt macro
#     agent_warehouse), before any model exists, so dbt's tables reach the roles by default privileges,
#   - loads dbt/dev/fixture.sql's sources and builds the sales, returns, finance, marketing, customer-actions, partner-outreach, recruitment and call-transcripts models,
#   - writes the catalog (make dbt-catalog),
#   - runs one turn of the semantic agent through ADK's Runner, in-memory sessions, a scripted model
#     (no model quota spent) and the real tools as agent_metrics and agent_audit,
# and asserts the answer's figure came from query_metrics, the call left its row in ops.agent_queries,
# and the freshness statement says the ledger is missing ("Freshness unknown").
# Expects `make services-up`; drops and recreates only the database agent_standalone.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DB=agent_standalone
OUT=${TMPDIR:-/tmp}/pplk8s-agent-standalone
fail() { echo "FAIL: $*" >&2; exit 1; }
compose() { docker compose -f "$REPO/platform/compose/compose.yaml" "$@"; }
psql_db() { compose exec -T warehouse psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"; }
mkdir -p "$OUT"

compose exec -T warehouse sh -c "dropdb -U warehouse --if-exists $DB && createdb -U warehouse $DB" >/dev/null 2>&1 ||
  fail "could not recreate $DB"
make -s -C "$REPO" agent-warehouse DBT_DBNAME="$DB" >"$OUT/agent-warehouse.log" 2>&1 ||
  { tail -20 "$OUT/agent-warehouse.log" >&2; fail "make agent-warehouse"; }
[ "$(psql_db -c "select to_regclass('ops.readiness') is null")" = t ] || fail "$DB has a readiness ledger"
echo "ok: make agent-warehouse created the roles' grants and ops.agent_queries in an empty $DB"

psql_db <"$REPO/dbt/dev/fixture.sql" 2>&1 | grep -v NOTICE || true
(cd "$REPO/dbt" && DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" DBT_PROFILES_DIR="$REPO/dbt" \
  uvx --quiet --with-requirements requirements.txt --from dbt-core dbt build --select tag:sales tag:returns tag:finance tag:marketing tag:customer_actions tag:partner_outreach tag:recruitment tag:call_transcripts --exclude tag:tlc) \
  >"$OUT/build.log" 2>&1 || { tail -30 "$OUT/build.log" >&2; fail "dbt build"; }
make -s -C "$REPO" dbt-catalog DBT_DBNAME="$DB" >"$OUT/catalog.log" 2>&1 || { tail -30 "$OUT/catalog.log" >&2; fail "make dbt-catalog"; }
echo "ok: the fixture's models and the catalog built in $DB"

(cd "$REPO/services/semantic-agent" && DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME="$DB" \
  DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics SEMANTIC_CATALOG="$REPO/dbt/target/catalog/agent.json" \
  uv run --quiet python - "$OUT/turn.json") <<'EOF' || fail "the agent's turn"
import json, sys
from semantic_agent.agent import build_agent
from tests.conftest import ScriptedLlm, final_text, run_turn

model = ScriptedLlm(steps=[
    ("query_metrics", {"metrics": ["net_revenue_eur"], "start_date": "2026-10-02", "end_date": "2026-10-02"}),
    "Net revenue was 861.4 EUR on 2 October 2026.",
])
events = run_turn(build_agent(model), "What was net revenue on 2 October 2026?")
(result,) = model.tool_results()
json.dump({"answer": final_text(events), "invocation": events[-1].invocation_id, "response": result["response"]},
          open(sys.argv[1], "w"), default=str)
EOF
rows=$(jq -c '.response.rows' "$OUT/turn.json")
statement=$(jq -r '.response.freshness.statement' "$OUT/turn.json")
echo "rows: $rows"
echo "freshness: $statement"
[ "$(jq -r '.response.error // empty' "$OUT/turn.json")" = "" ] || fail "query_metrics answered an error: $(jq -r .response.error "$OUT/turn.json")"
[ "$rows" = '[{"net_revenue_eur":861.4}]' ] || fail "expected net revenue 861.4, got $rows"
[[ "$statement" == "Freshness unknown: "* ]] || fail "expected 'Freshness unknown', got: $statement"
invocation=$(jq -r .invocation "$OUT/turn.json")
audited=$(psql_db -c "select count(*) from ops.agent_queries where invocation_id = '$invocation'
  and agent = 'semantic_agent' and tool = 'query_metrics' and rows_returned = 1 and freshness like 'Freshness unknown:%'")
[ "$audited" = 1 ] || fail "expected one audit row for invocation $invocation, got $audited"
echo "ok: the agent answered 861.4 through query_metrics as agent_metrics, said Freshness unknown, and left its audit row"
echo "PASS: agent standalone check"
