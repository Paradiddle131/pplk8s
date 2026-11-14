## 2026-11-03 — Semantic track — the native-mcp arm's ADK agent, built and run offline against a local MCP stand-in (#346)

- Done: `docs/research/semantic-bet/probes/328_mcp_agent.py` (ADK `McpToolset`s on Google's BigQuery and Knowledge Catalog MCP servers, read-only tools, a dry-run cost guard), `328_mcp_standin.py` (the same tool names over the Compose warehouse), `328_standin_check.sh`, the finding `docs/research/semantic-bet/findings/2026-11-03-346-mcp-offline.md`, the register's Q3 row.
- Evidence: Google's `execute_sql_readonly` takes no `maximumBytesBilled` (its schema, 2026-11-03), so the cap lives in the guard, which pinned the project and refused a 99,999,999,999-byte dry run; on `revenue_one_day` the agent headlined net revenue 861.40 instead of 868.65 in three runs of three, and never passed `lookup_context` an entry name.
- Open: Google's endpoints before and after the dbt import stay #328's, after #326 and #338.
