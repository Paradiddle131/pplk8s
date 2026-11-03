## 2026-11-03 — Semantic track — the custom-toolbox arm live: an ADK agent on generated MCP Toolbox tools only (#330)

- Done: `docs/research/semantic-bet/probes/330_toolbox_agent.py` (one `McpToolset` over HTTP to Toolbox 1.1.0 serving `330_tools.yaml` with `useClientOAuth`), `328_mcp_live.py --agent` to run any probe agent through the same scoring, the finding `docs/research/semantic-bet/findings/2026-11-03-330-toolbox-live.md` with its JSONL, the register's Q5 row (answered).
- Evidence: ten frozen cases, one run each: by hand 5 right, 3 declined, 2 confident-wrong (return rate by return date read as 0%, AOV over orders that include cancelled ones); on #328's seven, 4 right against native-mcp's 7; every statement dry-runs at 11.5 KB or less, 13 jobs and 170 MiB billed; cost and usage checks unchanged before and after.
- Open: the scorer reads the free model's reasoning inside the answer and misread 2 of 10 (#351); rates and the arms side by side (#333).
