## 2026-11-03 — Semantic track — confident-wrong turns hedged outside the list go to the blind judge (#366)

- Done: `bet_rule.HEDGE_LIKE`, a broad documented list of hedge-like phrases, picks the confident-wrong turns hedged in words outside the set's `hedges`; `bet_eval --judge` asks the blind judge about them twice (cached in `judge.jsonl`), `hedge_verdicts` lets it decide only whether the number is hedged, and `eval.md` counts the turns it moved.
- Evidence: 6 of 67 confident-wrong turns were candidates; 12 requests (20:30Z–20:31Z) moved 3 to wrong (2 `native-governed` run 1, 1 `native-shaped` run 3) and kept 3; `native-governed`'s confident-wrong rate went from 3.1% to 1.0% (`docs/research/semantic-bet/findings/2026-11-03-366-unlisted-hedges.md`); `make agent-test` (336 passed) and `make lint` pass.
- Open: turns logged after this pass need `--judge` again; declines worded as "not tracked or available" escape the decline patterns when unjudged.
