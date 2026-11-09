# Re-judging every judgeable answer with Claude Haiku (#428)

Written 2026-11-09T11:09Z; part of the fairness epic #424 (#425).

## What was run

- `python -m semantic_agent.bet_eval --set <set> --judge --concurrency 6` on `frozen`, `hard` and `hard-v2`, the judge `claude -p (haiku)` (#427): one fresh, tool-less `claude -p --model haiku` process a verdict, two verdicts a turn, on the owner's subscription; no OpenRouter request.
- The turns: every turn the report's scoring leaves unclear and every confident-wrong turn with a hedge-like phrase outside the set's list (`bet_eval.pending_verdicts` over `scored_logs`, #426), after the scorer changes of #430, #431 and #435 and the retirement of #434.
- One smoke pass of 2 verdicts first, read, then the rest; a second pass after #431 for the 65 turns it sent to the judge.

## What was observed (measured)

- `judge.jsonl` now holds 1336 Haiku verdict rows for 662 distinct turn answers (frozen, hard, hard-v2), beside the 606 Nemotron rows kept as history.
- Haiku's verdicts: right 863, wrong 190, declined 171, confident-wrong 112.
- Turns still waiting for a verdict after the passes: frozen 0, hard 0, hard-v2 0 (`--judge --dry-run`).
- Every verdict row carries a verdict (none came back without its VERDICT line), and no pass met a usage limit; 12 rows are a second copy of a verdict where two passes overlapped, and only one per attempt is read.

## Figures that moved

Each setup's accuracy and confident-wrong rate under the current scoring, read once with the Nemotron verdicts (which covered about 300 answers; the 408 it never saw counted as wrong) and once with Haiku's (every judgeable answer), all else equal (`bet_eval.results()` with `BET_JUDGE_BACKEND=openrouter`, then `claude`).
86 of 123 setup, model and set rows move; the rest are unchanged.

| Set | Setup | Model | Accuracy, Nemotron | Accuracy, Haiku | Change | Confident-wrong, Nemotron | Confident-wrong, Haiku | Change |
|---|---|---|---|---|---|---|---|---|
| frozen | `native-context-bare` | google-data-agent (MODEL_UNSPECIFIED, THINKING) | 92.1% | 98.7% | +6.6 | 1.3% | 1.3% | +0.0 |
| frozen | `native-bare` | google-data-agent (MODEL_UNSPECIFIED) | 74.1% | 80.3% | +6.1 | 18.9% | 18.9% | +0.0 |
| frozen | `native-context` | google-data-agent (MODEL_UNSPECIFIED) | 87.3% | 93.4% | +6.1 | 3.9% | 3.9% | +0.0 |
| frozen | `native-context-bare` | google-data-agent (MODEL_UNSPECIFIED) | 90.4% | 96.1% | +5.7 | 3.9% | 3.9% | +0.0 |
| frozen | `native-context-bare` | google-data-agent (MODEL_UNSPECIFIED, FAST) | 89.9% | 95.6% | +5.7 | 3.9% | 3.9% | +0.0 |
| frozen | `native-kc-reach` | google-data-agent (MODEL_UNSPECIFIED) | 83.8% | 89.5% | +5.7 | 7.9% | 7.9% | +0.0 |
| frozen | `native-mcp` | claude-sonnet-5-5 | 93.4% | 99.1% | +5.7 | 0.0% | 0.0% | +0.0 |
| frozen | `native-context-bare` | google-data-agent (LATEST_GA_MODEL) | 91.7% | 97.4% | +5.7 | 2.6% | 2.6% | +0.0 |
| frozen | `native-kc-max` | google-data-agent (MODEL_UNSPECIFIED) | 88.6% | 93.9% | +5.3 | 6.1% | 6.1% | +0.0 |
| frozen | `native-shaped` | google-data-agent (MODEL_UNSPECIFIED) | 65.4% | 69.7% | +4.4 | 6.6% | 6.6% | +0.0 |
| frozen | `native-graph` | google-data-agent (MODEL_UNSPECIFIED) | 65.8% | 69.7% | +3.9 | 8.8% | 9.2% | +0.4 |
| frozen | `native-governed` | google-data-agent (MODEL_UNSPECIFIED) | 78.5% | 82.5% | +3.9 | 1.8% | 2.2% | +0.4 |
| frozen | `native-mcp` | nvidia/nemotron-3.5-super-vl:free | 89.5% | 93.4% | +3.9 | 3.9% | 3.9% | +0.0 |
| frozen | `native-kc` | google-data-agent (MODEL_UNSPECIFIED) | 68.0% | 71.9% | +3.9 | 4.8% | 4.8% | +0.0 |
| frozen | `baseline` | claude-haiku-5-5 | 62.2% | 65.8% | +3.6 | 4.5% | 2.7% | -1.8 |
| frozen | `cc-native-mcp` | claude-code-strict (sonnet) | 96.1% | 99.1% | +3.1 | 0.9% | 0.4% | -0.4 |
| frozen | `custom-toolbox` | claude-haiku-5-5 | 50.0% | 52.6% | +2.6 | 2.2% | 2.2% | +0.0 |
| frozen | `native-mcp` | claude-haiku-5-5 | 95.2% | 97.8% | +2.6 | 0.4% | 0.4% | +0.0 |
| frozen | `baseline` | nvidia/nemotron-3.5-super-vl:free | 59.2% | 61.8% | +2.6 | 7.9% | 9.2% | +1.3 |
| frozen | `custom-toolbox` | nvidia/nemotron-3.5-super-vl:free | 43.4% | 46.1% | +2.6 | 5.3% | 5.3% | +0.0 |
| frozen | `native-context-python` | google-data-agent (MODEL_UNSPECIFIED) | 94.7% | 97.4% | +2.6 | 2.6% | 2.6% | +0.0 |
| frozen | `custom-toolbox` | claude-sonnet-5-5 | 48.7% | 50.9% | +2.2 | 1.8% | 1.8% | +0.0 |
| frozen | `cc-metricflow-compute` | claude-code-strict (haiku) | 86.9% | 88.9% | +2.0 | 0.5% | 0.5% | +0.0 |
| frozen | `custom-metricflow` | claude-opus-5-5 | 78.5% | 80.3% | +1.8 | 0.9% | 0.9% | +0.0 |
| frozen | `cc-native-mcp` | claude-code-strict (haiku) | 97.4% | 98.7% | +1.3 | 0.4% | 0.4% | +0.0 |
| frozen | `cc-metricflow` | claude-code (fresh-haiku) | 79.6% | 80.3% | +0.7 | 2.6% | 2.6% | +0.0 |
| frozen | `cc-metricflow-compute` | claude-code-strict (sonnet) | 88.7% | 89.2% | +0.5 | 0.0% | 0.0% | +0.0 |
| frozen | `custom-hybrid` | claude-haiku-5-5 | 89.5% | 89.9% | +0.4 | 0.0% | 0.0% | +0.0 |
| hard | `cc-metricflow` | claude-code (sonnet) | 47.5% | 52.5% | +5.0 | 7.5% | 7.5% | +0.0 |
| hard | `custom-lightdash` | nvidia/nemotron-3.5-super-vl:free | 35.0% | 40.0% | +5.0 | 12.5% | 10.0% | -2.5 |
| hard | `custom-toolbox` | claude-sonnet-5-5 | 49.2% | 54.2% | +5.0 | 5.8% | 3.3% | -2.5 |
| hard | `native-mcp` | claude-sonnet-5-5 | 88.8% | 93.8% | +5.0 | 0.0% | 0.0% | +0.0 |
| hard | `cc-native-mcp` | claude-code-strict (haiku) | 88.3% | 92.5% | +4.2 | 0.8% | 0.0% | -0.8 |
| hard | `custom-metricflow` | claude-sonnet-5-5 | 58.3% | 62.5% | +4.2 | 0.8% | 0.8% | +0.0 |
| hard | `custom-metricflow` | claude-haiku-5-5 | 80.0% | 84.2% | +4.2 | 1.7% | 0.8% | -0.8 |
| hard | `cc-native-mcp` | claude-code-strict (sonnet) | 89.2% | 92.5% | +3.3 | 1.7% | 0.0% | -1.7 |
| hard | `custom-metricflow` | nvidia/nemotron-3.5-super-vl:free | 75.0% | 78.3% | +3.3 | 4.2% | 3.3% | -0.8 |
| hard | `cc-metricflow` | claude-code (fresh-haiku) | 56.7% | 60.0% | +3.3 | 2.5% | 2.5% | +0.0 |
| hard | `cc-metricflow-compute` | claude-code-strict (haiku) | 83.9% | 87.2% | +3.3 | 0.0% | 0.0% | +0.0 |
| hard | `cc-metricflow` | claude-code-strict (sonnet) | 55.9% | 59.1% | +3.2 | 0.0% | 0.0% | +0.0 |
| hard | `baseline` | nvidia/nemotron-3.5-super-vl:free | 52.5% | 55.0% | +2.5 | 20.0% | 20.0% | +0.0 |
| hard | `cc-metricflow` | claude-code (fresh-opus) | 52.5% | 55.0% | +2.5 | 0.0% | 0.0% | +0.0 |
| hard | `custom-hybrid` | claude-haiku-5-5 | 85.0% | 87.5% | +2.5 | 0.0% | 0.0% | +0.0 |
| hard | `custom-hybrid` | nvidia/nemotron-3.5-super-vl:free | 87.5% | 90.0% | +2.5 | 0.0% | 0.0% | +0.0 |
| hard | `custom-toolbox` | claude-haiku-5-5 | 48.3% | 50.8% | +2.5 | 7.5% | 4.2% | -3.3 |
| hard | `custom-toolbox` | nvidia/nemotron-3.5-super-vl:free | 42.5% | 45.0% | +2.5 | 15.0% | 12.5% | -2.5 |
| hard | `native-mcp` | claude-haiku-5-5 | 85.8% | 88.3% | +2.5 | 4.2% | 2.5% | -1.7 |
| hard | `native-mcp` | nvidia/nemotron-3.5-super-vl:free | 95.0% | 97.5% | +2.5 | 0.0% | 0.0% | +0.0 |
| hard | `cc-metricflow-compute` | claude-code-strict (sonnet) | 76.7% | 78.9% | +2.2 | 2.2% | 2.2% | +0.0 |
| hard | `cc-metricflow` | claude-code-strict (haiku) | 73.1% | 75.3% | +2.2 | 0.0% | 0.0% | +0.0 |
| hard | `baseline` | claude-haiku-5-5 | 60.0% | 61.7% | +1.7 | 10.0% | 6.7% | -3.3 |
| hard | `cc-metricflow` | claude-code (fresh-sonnet) | 50.8% | 52.5% | +1.7 | 3.3% | 3.3% | +0.0 |
| hard | `native-graph` | google-data-agent (MODEL_UNSPECIFIED) | 60.0% | 61.7% | +1.7 | 19.2% | 18.3% | -0.8 |
| hard-v2 | `native-mcp` | claude-sonnet-5-5 | 88.8% | 95.0% | +6.2 | 0.0% | 0.0% | +0.0 |
| hard-v2 | `custom-lightdash` | nvidia/nemotron-3.5-super-vl:free | 35.0% | 40.0% | +5.0 | 12.5% | 10.0% | -2.5 |
| hard-v2 | `custom-toolbox` | claude-sonnet-5-5 | 49.2% | 54.2% | +5.0 | 5.8% | 4.2% | -1.7 |
| hard-v2 | `cc-native-mcp` | claude-code-strict (haiku) | 90.1% | 95.1% | +4.9 | 1.2% | 1.2% | +0.0 |
| hard-v2 | `custom-metricflow` | claude-sonnet-5-5 | 58.3% | 62.5% | +4.2 | 0.8% | 0.8% | +0.0 |
| hard-v2 | `cc-native-mcp` | claude-code-strict (opus) | 85.7% | 89.8% | +4.1 | 0.0% | 0.0% | +0.0 |
| hard-v2 | `cc-metricflow` | claude-code (sonnet) | 37.0% | 40.7% | +3.7 | 13.0% | 13.0% | +0.0 |
| hard-v2 | `cc-native-mcp` | claude-code-strict (sonnet) | 90.7% | 94.4% | +3.7 | 1.2% | 0.6% | -0.6 |
| hard-v2 | `custom-hybrid` | claude-haiku-5-5 | 85.0% | 88.3% | +3.3 | 0.0% | 0.0% | +0.0 |
| hard-v2 | `custom-metricflow` | claude-haiku-5-5 | 80.0% | 83.3% | +3.3 | 1.7% | 0.8% | -0.8 |
| hard-v2 | `custom-metricflow` | nvidia/nemotron-3.5-super-vl:free | 68.5% | 71.6% | +3.1 | 6.2% | 5.6% | -0.6 |
| hard-v2 | `cc-metricflow-compute` | claude-code-strict (opus) | 77.1% | 80.0% | +2.9 | 0.0% | 0.0% | +0.0 |
| hard-v2 | `cc-metricflow` | claude-code-strict (opus) | 44.4% | 47.2% | +2.8 | 5.6% | 5.6% | +0.0 |
| hard-v2 | `custom-toolbox` | claude-haiku-5-5 | 48.3% | 50.8% | +2.5 | 7.5% | 4.2% | -3.3 |
| hard-v2 | `custom-toolbox` | nvidia/nemotron-3.5-super-vl:free | 42.5% | 45.0% | +2.5 | 15.0% | 12.5% | -2.5 |
| hard-v2 | `native-mcp` | claude-haiku-5-5 | 85.8% | 88.3% | +2.5 | 4.2% | 2.5% | -1.7 |
| hard-v2 | `cc-metricflow` | claude-code (fresh-haiku) | 48.1% | 50.6% | +2.5 | 7.4% | 5.6% | -1.9 |
| hard-v2 | `baseline` | nvidia/nemotron-3.5-super-vl:free | 48.1% | 50.0% | +1.9 | 24.1% | 24.1% | +0.0 |
| hard-v2 | `cc-metricflow` | claude-code (fresh-opus) | 40.7% | 42.6% | +1.9 | 3.7% | 3.7% | +0.0 |
| hard-v2 | `native-bare` | google-data-agent (MODEL_UNSPECIFIED) | 71.6% | 73.5% | +1.9 | 22.2% | 22.2% | +0.0 |
| hard-v2 | `native-context-bare` | google-data-agent (MODEL_UNSPECIFIED, THINKING) | 97.5% | 99.4% | +1.9 | 0.0% | 0.0% | +0.0 |
| hard-v2 | `native-context-python` | google-data-agent (MODEL_UNSPECIFIED) | 96.3% | 98.1% | +1.9 | 0.0% | 0.0% | +0.0 |
| hard-v2 | `native-mcp` | nvidia/nemotron-3.5-super-vl:free | 96.3% | 98.1% | +1.9 | 0.0% | 0.0% | +0.0 |
| hard-v2 | `baseline` | claude-haiku-5-5 | 60.0% | 61.7% | +1.7 | 10.0% | 6.7% | -3.3 |
| hard-v2 | `native-graph` | google-data-agent (MODEL_UNSPECIFIED) | 60.0% | 61.7% | +1.7 | 19.2% | 18.3% | -0.8 |
| hard-v2 | `cc-metricflow-compute` | claude-code-strict (sonnet) | 73.2% | 74.8% | +1.6 | 7.3% | 6.5% | -0.8 |
| hard-v2 | `cc-metricflow-compute` | claude-code-strict (haiku) | 74.8% | 76.4% | +1.6 | 2.0% | 2.0% | +0.0 |
| hard-v2 | `cc-metricflow` | claude-code-strict (sonnet) | 55.8% | 57.4% | +1.6 | 6.2% | 6.2% | +0.0 |
| hard-v2 | `custom-hybrid` | nvidia/nemotron-3.5-super-vl:free | 79.6% | 80.9% | +1.2 | 6.8% | 6.2% | -0.6 |
| hard-v2 | `custom-metricflow-compute` | nvidia/nemotron-3.5-super-vl:free | 79.6% | 80.9% | +1.2 | 5.6% | 4.9% | -0.6 |
| hard-v2 | `cc-metricflow` | claude-code (fresh-sonnet) | 39.5% | 40.7% | +1.2 | 6.8% | 6.8% | +0.0 |
| hard-v2 | `native-context` | google-data-agent (MODEL_UNSPECIFIED) | 96.3% | 97.5% | +1.2 | 0.0% | 0.0% | +0.0 |
| hard-v2 | `native-kc-max` | google-data-agent (MODEL_UNSPECIFIED) | 94.4% | 95.1% | +0.6 | 0.6% | 0.6% | +0.0 |

## What it means

- The biggest moves are on Google's data agents and `native-mcp` on the frozen set (about +4 to +7 points): their long, explanatory answers carry small expected numbers beside other figures, the turns #426 found the old judge path never saw.
- The free-model setups of ours move 0 to +5 points; confident-wrong rates fall slightly where the judge read a caveat as a hedge.
- So the old scores penalised verbose answers; reading the comparisons again under the rebuilt report is the epic's last step (#424).

## What stays unknown

- How often Haiku's verdict is right: #429 measures it on a blind sample.

## Sources

- `judge.jsonl`, `scored-runs.jsonl`, `results.json` at this commit; RULE.md § Changes since freezing, 2026-11-09 (#427).
