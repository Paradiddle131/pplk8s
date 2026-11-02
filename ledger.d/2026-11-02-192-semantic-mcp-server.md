## 2026-11-02 — Semantic track — the three metric tools over MCP (#192)

- Done: `semantic_agent.mcp_server` serves `list_metrics`, `describe_metric` and `query_metrics` over MCP (streamable HTTP, MCP SDK 2.3.0), each data call audited as the agent its bearer token names and given its freshness through `guard.guarded`, the code ADK's callback now calls too.
- Done: `make agent-mcp` and `make agent-mcp-check` (a scripted MCP client, no model); `examples/mcp_client` for `adk run`; the agent image goes to 0.1.39.
- Evidence: `make agent-mcp-check` PASS (three tools, 861.4 with its freshness, one audit row as the client, 401 without a token); `adk run` on a free model answered the eval's `net_revenue_one_day` with 964.19 EUR, equal to its expected SQL.
- Decisions: SL-20 in `semantic/PLAN.md`; one lesson in its § 6.
- Open: none.
