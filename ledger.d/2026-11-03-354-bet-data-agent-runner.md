## 2026-11-03 — Semantic track — the data-agent arms in the bet's runner, and native-kc's first pass (#354, first part)

- Done: `docs/research/semantic-bet/probes/354_data_agent.py` asks a data-agent arm (`bet-kc`, `bet-shaped`, `bet-graph`) every turn of a frozen case in one stateless `:chat` conversation, for `328_mcp_live.py --agent 354_data_agent.py --arm <arm>`; the runner now writes eval.md at the rule's k = 3 whatever a pass asks.
- Evidence: live on `bet-kc`, two cases (one two-turn) end to end in 3 chats, gcp cost and usage checks ok and unchanged before and after; the finding `docs/research/semantic-bet/findings/2026-11-03-354-data-agent-arms.md`.
- Done: `bet-kc`, `bet-shaped` and `bet-graph` republished with the `legacy` tables in reach (`354_data_agent.py --legacy`); `native-kc`'s first pass: run 1 of all 96 cases (64.6% right, 4.2% confident-wrong) and 16 of run 2, in `eval-native-kc.jsonl`, each row naming the data agent's own model.
- Open: the remaining passes; how RULE.md compares a managed arm (Google's model) with ours (the owner's call, #333).
