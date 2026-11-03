## 2026-11-03 — Semantic track — the blind judge decides the turns the code cannot (#358)

- Done: `bet_rule.py` holds the judge's blind prompt and how two verdicts combine; `bet_eval.py --judge` asks a free OpenRouter model (`model.build_judge()`, `nvidia/nemotron-3-ultra-550b-a55b:free`) twice per unclear turn, caches each verdict in `docs/research/semantic-bet/judge.jsonl` beside the arms' append-only logs, applies them on read, and `eval.md` lists the turns still unclear.
- Evidence: 32 requests judged all 16 unclear turns (20:02Z–20:04Z); every pair agreed (12 declined, 4 wrong), so no turn stays unclear and no arm's accuracy or confident-wrong rate moved (`docs/research/semantic-bet/findings/2026-11-03-358-blind-judge.md`); `make agent-test` and `make lint` pass.
- Open: turns logged after this pass need `--judge` again on the merged logs; the judge's agreement with a human grader is unmeasured.
