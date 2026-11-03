## 2026-11-03 — Semantic track — the data-agent arms wired into the bet's runner (#354, first part)

- Done: `docs/research/semantic-bet/probes/354_data_agent.py` asks a data-agent arm (`bet-kc`, `bet-shaped`, `bet-graph`) every turn of a frozen case in one stateless `:chat` conversation, for `328_mcp_live.py --agent 354_data_agent.py --arm <arm>`; the runner now writes eval.md at the rule's k = 3 whatever a pass asks.
- Evidence: live on `bet-kc`, two cases (one two-turn) end to end in 3 chats, gcp cost and usage checks ok and unchanged before and after; the finding `docs/research/semantic-bet/findings/2026-11-03-354-data-agent-arms.md`.
- Open: republish each data-agent arm with the `legacy` schema in reach (RULE.md), then the passes.
