#!/usr/bin/env bash
# What it measures (#346, offline): that probes/328_mcp_agent.py discovers and filters the MCP tools, that its
# cost guard pins the project and refuses a query over the cap, and that it answers one frozen covered
# question (revenue_one_day, expected 2 October 2026's revenue_eur in gold.daily_sales) through
# probes/328_mcp_standin.py, with no Google call. The answer spends a few OpenRouter free-tier requests.
# How to run (from the repo root, after make services-up and tests/e2e/agent-fixture.sh):
#   bash docs/research/semantic-bet/probes/328_standin_check.sh
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../../.." && pwd)"
PROBES="$REPO/docs/research/semantic-bet/probes"
cd "$REPO/services/semantic-agent"
export DBT_DBNAME=dbt_dev
pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true' EXIT
serve() { # port, dry-run bytes
  STANDIN_PORT=$1 STANDIN_DRY_BYTES=$2 uv run python "$PROBES/328_mcp_standin.py" &
  pids+=($!)
  for _ in $(seq 1 30); do curl -s -o /dev/null "127.0.0.1:$1/bigquery/mcp" && return; sleep 1; done
  echo "the stand-in on $1 did not start" >&2
  exit 1
}
serve 8766 0
serve 8767 99999999999

echo "== tools discovered, and the guard"
uv run python - "$PROBES/328_mcp_agent.py" <<'PY'
import asyncio
import importlib.util
import os
import sys

def load(bigquery, catalog):
    os.environ["BET_BIGQUERY_MCP"], os.environ["BET_CATALOG_MCP"] = bigquery, catalog
    spec = importlib.util.spec_from_file_location("bet_mcp", sys.argv[1])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

async def check(port, query):
    m = load(f"http://127.0.0.1:{port}/bigquery/mcp", f"http://127.0.0.1:{port}/catalog/mcp")
    agent = m.build_agent()
    tools = [t for toolset in agent.tools for t in await toolset.get_tools()]
    print(f"  port {port}: tools", sorted(t.name for t in tools))
    sql = next(t for t in tools if t.name == "execute_sql_readonly")
    args = {"projectId": "someone-elses-project", "query": query}
    refused = await m.cost_guard(sql, args, None)
    print(f"  port {port}: projectId after the guard {args['projectId']!r}; guard result {refused}")
    for toolset in agent.tools:
        await toolset.close()

asyncio.run(check(8766, "select 1"))
asyncio.run(check(8767, "select 1"))
PY

echo "== one frozen covered question (revenue_one_day)"
BET_BIGQUERY_MCP=http://127.0.0.1:8766/bigquery/mcp BET_CATALOG_MCP=http://127.0.0.1:8766/catalog/mcp \
  uv run python "$PROBES/328_mcp_agent.py" "How much revenue did we make on 2 October 2026?"
echo "== expected"
docker compose -f "$REPO/platform/compose/compose.yaml" exec -T warehouse psql -U warehouse -d dbt_dev -qAt \
  -c "select revenue_eur from gold.daily_sales where order_date = '2026-10-02'"
