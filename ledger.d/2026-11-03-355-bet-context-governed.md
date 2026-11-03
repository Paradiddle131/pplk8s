## 2026-11-03 — Semantic track — native-context and native-governed on the frozen set, all 3 runs (#355)

- Done: `354_data_agent.py --copy` published `bet-context` and `bet-governed` from the main track's `pplk8s-semantic` and `pplk8s-governed` published contexts, plus the legacy tables; the first pass, side by side (16:42Z–17:12Z), logged run 1 of all 96 cases on each and part of run 2.
- Evidence: on run 1, `native-context` 87.5% right, 6.2% confident-wrong; `native-governed` 72.9%, 3.1%; against `native-kc`'s 64.6% and 4.2% (`eval.md`, `docs/research/semantic-bet/findings/2026-11-03-355-context-governed.md`); gcp cost and usage checks ok and unchanged before and after.
- Done: runs 2 and 3 of both arms (20:00Z–20:38Z, 139 runs and 147 chats of `native-context`, 127 and 133 of `native-governed`, no 429): all 3 runs of all 96 cases each; `native-context` 87.2% right, 5.2% confident-wrong, pass^3 83.3%; `native-governed` 72.9%, 1.7%, 70.8%; `native-context` is the managed best among all five data-agent arms, every other one below it by a paired interval excluding zero.
- Done: a dropped chat stream (`ConnectionResetError`, 20:25Z) is now a failed chat the runner asks again, not the end of the pass (`354_data_agent.py`).
- Evidence: `eval.md`; the finding; gcp cost and usage checks ok before and after each pass, cost $0.000010 unchanged.
- Open: how much of `native-context`'s lead its verified queries and its reach carry (#357).
