#!/usr/bin/env bash
# The semantic layer's tools over MCP (semantic/PLAN.md SL-20), with no model: on the agents' fixture
# in dbt_dev (agent-fixture.sh) it serves `python -m semantic_agent.mcp_server` on localhost as
# agent_metrics, with one client token named for this run, then a scripted MCP client
#   - lists the tools and finds exactly list_metrics, describe_metric and query_metrics,
#   - asks query_metrics for net revenue on 2 October 2026 and gets 861.4 with the freshness statement,
#   - finds the call's row in ops.agent_queries, written as the client its token names,
# and a call without a token, or with an unknown one, is refused with 401 and leaves no row.
# Expects `make services-up`.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DB=dbt_dev
PORT=${MCP_PORT:-8765}
URL="http://127.0.0.1:$PORT/mcp"
OUT=${TMPDIR:-/tmp}/pplk8s-agent-mcp
fail() { echo "FAIL: $*" >&2; exit 1; }
psql_db() {
  docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse \
    psql -U warehouse -d "$DB" -v ON_ERROR_STOP=1 -qAt "$@"
}
mkdir -p "$OUT"

DB=$DB "$REPO/tests/e2e/agent-fixture.sh"

run=$(head -c4 /dev/urandom | od -An -tx1 | tr -d ' \n')
agent="mcp_check_$run"
token=$(head -c24 /dev/urandom | od -An -tx1 | tr -d ' \n')
export DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=$DB DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics \
  SEMANTIC_CATALOG="$REPO/dbt/target/catalog/agent.json" SEMANTIC_MCP_PORT=$PORT \
  SEMANTIC_MCP_CLIENTS="$agent=$token"
(cd "$REPO/services/semantic-agent" && exec uv run --quiet python -m semantic_agent.mcp_server) >"$OUT/server.log" 2>&1 &
server=$!
trap 'kill $server 2>/dev/null || true' EXIT
for _ in $(seq 60); do
  curl -s -o /dev/null "http://127.0.0.1:$PORT/" && break
  kill -0 $server 2>/dev/null || { tail -20 "$OUT/server.log" >&2; fail "the MCP server exited"; }
  sleep 1
done
echo "ok: the MCP server serves $URL as agent_metrics, with one client token ($agent)"

refused() {
  curl -s -o /dev/null -w '%{http_code}' -X POST "$URL" "$@" \
    -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"query_metrics","arguments":{"metrics":["net_revenue_eur"]}}}'
}
[ "$(refused)" = 401 ] || fail "a call without a token was not refused with 401"
[ "$(refused -H 'Authorization: Bearer not-a-client')" = 401 ] || fail "a call with an unknown token was not refused with 401"
echo "ok: a call without a token, or with an unknown one, is refused with 401"

(cd "$REPO/services/semantic-agent" && uv run --quiet python - "$URL" "$token" "$OUT/call.json") <<'EOF' || fail "the scripted MCP client"
import asyncio, json, sys

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

url, token, out = sys.argv[1:]


async def main():
    http = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=120)
    async with Client(streamable_http_client(url, http_client=http)) as client:
        listed = sorted(tool.name for tool in (await client.list_tools()).tools)
        args = {"metrics": ["net_revenue_eur"], "start_date": "2026-10-02", "end_date": "2026-10-02"}
        result = await client.call_tool("query_metrics", args)
        return {"tools": listed, "is_error": result.is_error, "response": result.structured_content}


json.dump(asyncio.run(main()), open(out, "w"), default=str)
EOF
tools=$(jq -c .tools "$OUT/call.json")
rows=$(jq -c .response.rows "$OUT/call.json")
statement=$(jq -r .response.freshness.statement "$OUT/call.json")
echo "tools: $tools"
echo "rows: $rows"
echo "freshness: $statement"
[ "$tools" = '["describe_metric","list_metrics","query_metrics"]' ] || fail "expected the three tools, got $tools"
[ "$(jq -r '.response.error // empty' "$OUT/call.json")" = "" ] || fail "query_metrics answered an error: $(jq -r .response.error "$OUT/call.json")"
[ "$rows" = '[{"net_revenue_eur":861.4}]' ] || fail "expected net revenue 861.4, got $rows"
# Net revenue reads sales and returns: the fixture's sales.silver is long past its 36 h deadline,
# and returns.silver has none.
[[ "$statement" == *"Late: sales.silver"* && "$statement" == *"returns.silver"* ]] ||
  fail "expected the freshness of sales.silver (late) and returns.silver, got: $statement"
echo "ok: the scripted client listed the three tools and query_metrics answered 861.4 with its freshness"

audited=$(psql_db -c "select count(*) from ops.agent_queries where agent = '$agent' and tool = 'query_metrics'
  and metrics = array['net_revenue_eur'] and rows_returned = 1 and call_id is not null
  and freshness = \$\$$statement\$\$")
[ "$audited" = 1 ] || fail "expected one audit row written as $agent, got $audited"
others=$(psql_db -c "select count(*) from ops.agent_queries where agent = '$agent'")
[ "$others" = 1 ] || fail "expected only the answered call audited as $agent, got $others rows"
echo "ok: the call left one row in ops.agent_queries as $agent, holding the statement the client was shown"
echo "PASS: agent MCP check"
