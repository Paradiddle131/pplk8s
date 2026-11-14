## 2026-11-06 — Semantic track — bet_eval and the report learn a versioned set; v1's runs carried into hard-v2 (#378)

- Done: `bet_eval --set hard-v2` reads `semantic_bet_hard_v2.yaml`, logs to `eval-hard-v2-*.jsonl`, has v1's canary, and reports each arm's new cases apart (`new` in `results.json`, all and by group); the rule's verdict still reads the frozen set and v1 (`DECIDING`), so hard-v2's section in `eval.md` is descriptive until the owner's go.
  `semantic_agent.bet_carry` copies the superseded set's runs and judge verdicts of every unchanged case, each row with `carried_from` and the SHA-256 of its scoring inputs, refuses a changed case, and copies nothing twice; run on the logs: 43 cases, 3,222 runs and 84 verdicts carried, a second run 0.
  `report/build.py` knows set families: it shows `hard` until `--show hard-v2`, files logs by their longest prefix, and puts the other version in an appendix labelled "not yet adopted" or "superseded".
- Evidence: `make agent-test` → `412 passed`; `make lint` passes (after `make tools` installed tofu and tflint); the probes' ruff gates pass; `results.json`'s frozen and hard rows, pairs, managed best and ties are equal before and after; the page builds, and Chromium at 1280 and 400 px shows the appendix with no console error and no horizontal scroll.
- Open: #379, the runs of hard-v2's 15 new cases.
