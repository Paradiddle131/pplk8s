## 2026-11-07 — Semantic track — the data agent with Python analysis on (#333)

- Done: `native-context-python` joined under RULE.md (`bet-context` with Python analysis on, logging each Python step as `python_analysis`), and ran one run a question on the extended hard set (92.7% right, 0.0% confident-wrong) and the frozen set (90.8%, 2.6%).
- Evidence: `findings/2026-11-07-python-analysis.md`; no Python step in 131 runs; `test_bet_tools.py` pins the one difference; `gcp-cost-check` $0.000010.
- Open: nothing; k = 3 not run, since the switch changed nothing the agent did.
