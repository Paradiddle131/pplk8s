## 2026-11-03 — Semantic track — the native-mcp agent with the governed tables out of reach, run 1 (#350)

- Done: `BET_SQL_DENY` in `docs/research/semantic-bet/probes/328_mcp_agent.py` (the guard refuses SQL naming `governed`, `gold`, `exposed`, `legacy` or `bet_*`, and `execute_query`), run 1 of twelve frozen cases (#328's seven and the other five traps), the finding `docs/research/semantic-bet/findings/2026-11-03-350-mcp-silver.md` with its JSONL, the register's Q3 row.
- Evidence: 11 of 12 right with only `silver` in reach (7 of 7 on #328's cases), the one miss the fiscal-quarter trap (calendar Q3 read for fiscal Q3); the guard refused 11 calls in 9 cases and the agent rewrote each over `silver` with the imported definitions; 19 jobs, 230 MiB billed; cost and usage checks unchanged before and after.
- Run 2 (09:10Z to 09:21Z, the reasoning kept out of the scored answer): 12 of 12 right, the fiscal trap included; 23 of 24 over two runs.
- Run 3 (09:41Z to 10:17Z, through an outage of the free model's provider): 7 of 7 right on the cases it reached, the fiscal trap included; 30 of 31 over the logged runs. The probes now leave a failed model call out of the log instead of scoring its error text (two had scored confident-wrong on "Retried: 2 times").
- Open: run 3's other five cases (the next wake on #350); rates beside the other arms (#333).
