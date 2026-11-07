## 2026-11-07 — Semantic track — the MCP cost guards quote BigQuery's reason for a failed dry run (#392)

- Done: `probes/328_mcp_agent.py` `dry_run_refusal` quotes the plain-text error Google's BigQuery MCP server returns for a failed dry run (it was `{}`, since only JSON was parsed); `probes/387_mcp_guard.py` uses it, so `native-mcp` and `cc-native-mcp` change together; RULE.md § Changes since freezing dated with the owner's words.
- Evidence: `tests/test_bet_tools.py` 11 passed, three new (each guard on an `isError` text result, the JSON path unchanged); ruff check and format clean on the probes.
- Held: merged into the semantic bet's train after `native-mcp`'s extended-hard-set k = 3 pass is whole, so no pass mixes the two refusal texts.
