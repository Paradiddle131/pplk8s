## 2026-11-03 — Semantic track — native-context and native-governed on the frozen set, first pass (#355)

- Done: `354_data_agent.py --copy` published `bet-context` and `bet-governed` from the main track's `pplk8s-semantic` and `pplk8s-governed` published contexts, plus the legacy tables; the first pass, side by side (16:42Z–17:12Z), logged run 1 of all 96 cases on each and part of run 2.
- Evidence: on run 1, `native-context` 87.5% right, 6.2% confident-wrong; `native-governed` 72.9%, 3.1%; against `native-kc`'s 64.6% and 4.2% (`eval.md`, `docs/research/semantic-bet/findings/2026-11-03-355-context-governed.md`); gcp cost and usage checks ok and unchanged before and after.
- Open: runs 2 and 3 (next passes); whether `native-context`'s verified queries overlap the frozen questions.
