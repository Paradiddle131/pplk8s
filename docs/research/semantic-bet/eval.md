# Every arm on the bet's sets

Each set is scored on its own under [the rule](RULE.md), with its own comparison against the managed best: [the frozen set](#every-arm-on-the-frozen-set), then [the hard set](#every-arm-on-the-hard-set), then [the hard set v2](#every-arm-on-the-hard-set-v2) (#356, #364).

## Every arm on the frozen set

Written 2026-11-09T12:04Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 76 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `claude -p (haiku)` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
14 of `baseline`'s 262 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 42 of 76 cases; runs finished: baseline 42 of 228, custom-metricflow 89 of 228, custom-hybrid 42 of 228, custom-metricflow-compute 94 of 228, custom-lightdash 76 of 228, custom-toolbox 76 of 228, native-mcp 76 of 228; model responses spent: baseline 161, custom-metricflow 343, custom-hybrid 165, custom-metricflow-compute 346, custom-lightdash 151, custom-toolbox 129, native-mcp 452.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-metricflow-compute` | `custom-lightdash` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|---|---|
| Accuracy | 90.5% | 100.0% | 100.0% | 100.0% | 66.7% | 59.5% | 97.6% |
| Confident-wrong | 4.8% | 0.0% | 0.0% | 0.0% | 11.9% | 7.1% | 2.4% |
| pass^1 | 90.5% | 100.0% | 100.0% | 100.0% | 66.7% | 59.5% | 97.6% |
| `conversation` (6) accuracy | 83.3% | 100.0% | 100.0% | 100.0% | 33.3% | 83.3% | 100.0% |
| `covered` (42) accuracy | 90.5% | 100.0% | 100.0% | 100.0% | 66.7% | 59.5% | 97.6% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| `planted` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 100.0% |
| `trap` (8) accuracy | 75.0% | 100.0% | 100.0% | 100.0% | 62.5% | 62.5% | 87.5% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.095 [+0.024, +0.190]: a difference.
- Confident-wrong: -0.048 [-0.119, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 9 (`baseline` 2 wrong to unclear; `custom-lightdash` 1 unclear to declined; `custom-metricflow` 1 unclear to declined; `custom-toolbox` 2 wrong to unclear; `native-mcp` 1 right to unclear; `native-mcp` 2 wrong to unclear).

Turns judged: 19 (13 the code left unclear, 6 confident-wrong with a hedge outside the list); verdicts that stood: 19.
Confident-wrong turns the judge moved: 4 of 6 (4 to wrong, hedged; 0 to unclear).

### `claude-haiku-5-5`

Scored on partial: 1 run(s) of 71 of 76 cases; runs finished: baseline 220 of 228, custom-metricflow 225 of 228, custom-hybrid 225 of 228, custom-toolbox 226 of 228, native-mcp 227 of 228; model responses spent: baseline 785, custom-metricflow 753, custom-hybrid 805, custom-toolbox 402, native-mcp 1075.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 67.6% | 90.1% | 91.5% | 54.9% | 100.0% |
| Confident-wrong | 2.8% | 0.0% | 0.0% | 1.4% | 0.0% |
| pass^1 | 67.6% | 90.1% | 91.5% | 54.9% | 100.0% |
| `conversation` (6) accuracy | 100.0% | 100.0% | 100.0% | 83.3% | 100.0% |
| `covered` (57) accuracy | 78.9% | 100.0% | 100.0% | 59.6% | 100.0% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% | 75.0% | 100.0% |
| `trap` (9) accuracy | 66.7% | 100.0% | 100.0% | 66.7% | 100.0% |
| `uncovered` (14) accuracy | 21.4% | 50.0% | 57.1% | 35.7% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.225 [+0.127, +0.324]: a difference.
- Confident-wrong: -0.028 [-0.070, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 76 (`baseline` 7 confident-wrong to right; `baseline` 2 right to unclear; `baseline` 6 wrong to unclear; `custom-hybrid` 9 confident-wrong to right; `custom-hybrid` 1 right to unclear; `custom-hybrid` 13 unclear to right; `custom-metricflow` 3 confident-wrong to right; `custom-metricflow` 1 confident-wrong to wrong; `custom-metricflow` 10 unclear to right; `custom-toolbox` 1 confident-wrong to right; `custom-toolbox` 6 wrong to unclear; `native-mcp` 7 confident-wrong to right; `native-mcp` 3 unclear to right; `native-mcp` 1 wrong to right; `native-mcp` 6 wrong to unclear).

Turns judged: 35 (21 the code left unclear, 14 confident-wrong with a hedge outside the list); verdicts that stood: 34.
Confident-wrong turns the judge moved: 12 of 14 (11 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `signups_september` run 1 turn 1: wrong / declined

### `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 228 of 228, custom-toolbox 228 of 228, native-mcp 228 of 228; model responses spent: custom-metricflow 743, custom-toolbox 394, native-mcp 1016.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 83.3% | 50.9% | 99.1% |
| Confident-wrong | 0.0% | 1.8% | 0.0% |
| pass^3 | 81.6% | 50.0% | 98.7% |
| `conversation` (7) accuracy | 100.0% | 66.7% | 100.0% |
| `covered` (61) accuracy | 100.0% | 55.2% | 98.9% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 50.0% | 83.3% |
| `trap` (10) accuracy | 100.0% | 60.0% | 100.0% |
| `uncovered` (15) accuracy | 15.6% | 33.3% | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 27 (`custom-metricflow` 2 confident-wrong to right; `custom-metricflow` 1 confident-wrong to wrong; `custom-metricflow` 1 unclear to declined; `custom-metricflow` 2 unclear to right; `custom-metricflow` 1 wrong to right; `custom-toolbox` 1 confident-wrong to right; `custom-toolbox` 5 wrong to unclear; `native-mcp` 7 right to unclear; `native-mcp` 1 unclear to right; `native-mcp` 6 wrong to unclear).

Turns judged: 27 (23 the code left unclear, 4 confident-wrong with a hedge outside the list); verdicts that stood: 27.
Confident-wrong turns the judge moved: 2 of 4 (2 to wrong, hedged; 0 to unclear).

### `claude-opus-5-5`

Scored on partial: 1 run(s) of 74 of 76 cases; runs finished: custom-metricflow 226 of 228; model responses spent: custom-metricflow 743.

| | `custom-metricflow` |
|---|---|
| Accuracy | 82.4% |
| Confident-wrong | 1.4% |
| pass^1 | 82.4% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 100.0% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (13) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 5 (`custom-metricflow` 4 right to unclear; `custom-metricflow` 1 unclear to right).

Turns judged: 6 (5 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 6.
Confident-wrong turns the judge moved: 1 of 1 (1 to wrong, hedged; 0 to unclear).

### `claude-code-strict (haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 228 of 228, cc-metricflow 228 of 228, cc-native-mcp 228 of 228; model responses spent: cc-metricflow-compute 246, cc-metricflow 246, cc-native-mcp 246.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 90.4% | 88.6% | 98.7% |
| Confident-wrong | 0.4% | 0.4% | 0.4% |
| pass^3 | 89.5% | 86.8% | 96.1% |
| `conversation` (7) accuracy | 100.0% | 100.0% | 95.2% |
| `covered` (61) accuracy | 100.0% | 100.0% | 98.4% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 91.7% |
| `trap` (10) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (15) accuracy | 51.1% | 42.2% | 100.0% |

Turns judged: 26 (26 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 25.

Turns still unclear after judging (counted as wrong):

- `cc-metricflow-compute` `bet_cart_to_checkout_minutes` run 1 turn 1: declined / wrong

### `claude-code-strict (sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 228 of 228, cc-metricflow 228 of 228, cc-native-mcp 228 of 228; model responses spent: cc-metricflow-compute 246, cc-metricflow 246, cc-native-mcp 246.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 90.8% | 85.1% | 99.1% |
| Confident-wrong | 0.0% | 0.9% | 0.4% |
| pass^3 | 89.5% | 82.9% | 98.7% |
| `conversation` (7) accuracy | 100.0% | 100.0% | 100.0% |
| `covered` (61) accuracy | 100.0% | 99.5% | 100.0% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% |
| `trap` (10) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (15) accuracy | 53.3% | 26.7% | 95.6% |

Turns judged: 24 (23 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 24.
Confident-wrong turns the judge moved: 1 of 1 (1 to wrong, hedged; 0 to unclear).

### `claude-code (haiku)`

Scored on partial: 1 run(s) of 76 of 76 cases; runs finished: cc-metricflow 76 of 228; model responses spent: cc-metricflow 82.

| | `cc-metricflow` |
|---|---|
| Accuracy | 75.0% |
| Confident-wrong | 2.6% |
| pass^1 | 75.0% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 93.4% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 75.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 4 (`cc-metricflow` 1 confident-wrong to wrong; `cc-metricflow` 3 unclear to declined).

### `claude-code (sonnet)`

Scored on partial: 1 run(s) of 76 of 76 cases; runs finished: cc-metricflow 76 of 228; model responses spent: cc-metricflow 82.

| | `cc-metricflow` |
|---|---|
| Accuracy | 80.3% |
| Confident-wrong | 1.3% |
| pass^1 | 80.3% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 100.0% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 2 (`cc-metricflow` 1 unclear to declined; `cc-metricflow` 1 wrong to declined).

### `claude-code (opus)`

Scored on partial: 1 run(s) of 76 of 76 cases; runs finished: cc-metricflow 76 of 228; model responses spent: cc-metricflow 82.

| | `cc-metricflow` |
|---|---|
| Accuracy | 80.3% |
| Confident-wrong | 1.3% |
| pass^1 | 80.3% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 100.0% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 3 (`cc-metricflow` 2 confident-wrong to wrong; `cc-metricflow` 1 unclear to declined).

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

### `claude-code (fresh-haiku)`

Scored on partial: 1 run(s) of 76 of 76 cases; runs finished: cc-metricflow 226 of 228; model responses spent: cc-metricflow 244.

| | `cc-metricflow` |
|---|---|
| Accuracy | 81.6% |
| Confident-wrong | 1.3% |
| pass^1 | 81.6% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (61) accuracy | 98.4% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 13.3% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 4 (`cc-metricflow` 1 confident-wrong to right; `cc-metricflow` 2 confident-wrong to wrong; `cc-metricflow` 1 right to unclear).

Turns judged: 3 (3 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 3.

### `claude-code (fresh-sonnet)`

Scored on partial: 1 run(s) of 76 of 76 cases; runs finished: cc-metricflow 227 of 228; model responses spent: cc-metricflow 245.

| | `cc-metricflow` |
|---|---|
| Accuracy | 80.3% |
| Confident-wrong | 1.3% |
| pass^1 | 80.3% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 98.4% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 75.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 6.7% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 4 (`cc-metricflow` 3 confident-wrong to wrong; `cc-metricflow` 1 unclear to declined).

### `claude-code (fresh-opus)`

Scored on partial: 1 run(s) of 37 of 76 cases; runs finished: cc-metricflow 37 of 228; model responses spent: cc-metricflow 41.

| | `cc-metricflow` |
|---|---|
| Accuracy | 86.5% |
| Confident-wrong | 0.0% |
| pass^1 | 86.5% |
| `conversation` (4) accuracy | 100.0% |
| `covered` (32) accuracy | 100.0% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (2) accuracy | 100.0% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (5) accuracy | 0.0% |

### `claude-code (subject-haiku)`

Scored on partial: 1 run(s) of 76 of 76 cases; runs finished: cc-metricflow 76 of 228; model responses spent: cc-metricflow 82.

| | `cc-metricflow` |
|---|---|
| Accuracy | 77.6% |
| Confident-wrong | 3.9% |
| pass^1 | 77.6% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 95.1% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 6.7% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 1 (`cc-metricflow` 1 unclear to declined).

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 75 of 76 cases; runs finished: native-bare 227 of 228, native-context-bare 228 of 228, native-context-python 76 of 228, native-context 228 of 228, native-governed 228 of 228, native-graph 228 of 228, native-kc-max 228 of 228, native-kc-reach 228 of 228, native-kc 228 of 228, native-shaped 228 of 228; model responses spent: native-bare 245, native-context-bare 246, native-context-python 82, native-context 246, native-governed 246, native-graph 246, native-kc-max 246, native-kc-reach 246, native-kc 246, native-shaped 246.

| | `native-bare` | `native-context-bare` | `native-context-python` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 78.7% | 96.0% | 97.3% | 94.7% | 82.7% | 68.0% | 93.3% | 89.3% | 72.0% | 69.3% |
| Confident-wrong | 20.0% | 4.0% | 2.7% | 4.0% | 2.7% | 9.3% | 6.7% | 8.0% | 5.3% | 6.7% |
| pass^1 | 78.7% | 96.0% | 97.3% | 94.7% | 82.7% | 68.0% | 93.3% | 89.3% | 72.0% | 69.3% |
| `conversation` (7) accuracy | 42.9% | 100.0% | 100.0% | 100.0% | 100.0% | 71.4% | 71.4% | 42.9% | 85.7% | 57.1% |
| `covered` (60) accuracy | 75.0% | 100.0% | 100.0% | 98.3% | 93.3% | 68.3% | 91.7% | 88.3% | 73.3% | 68.3% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 75.0% | 100.0% | 100.0% | 100.0% | 75.0% | 75.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `trap` (9) accuracy | 55.6% | 100.0% | 100.0% | 100.0% | 100.0% | 55.6% | 88.9% | 88.9% | 55.6% | 44.4% |
| `uncovered` (15) accuracy | 93.3% | 80.0% | 86.7% | 80.0% | 40.0% | 66.7% | 100.0% | 93.3% | 66.7% | 73.3% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 118 (`native-bare` 10 right to unclear; `native-bare` 6 wrong to unclear; `native-context` 9 right to unclear; `native-context` 6 wrong to unclear; `native-context-bare` 7 right to unclear; `native-context-bare` 6 wrong to unclear; `native-governed` 4 right to unclear; `native-governed` 6 wrong to unclear; `native-graph` 4 right to unclear; `native-graph` 1 wrong to right; `native-graph` 6 wrong to unclear; `native-kc` 3 right to unclear; `native-kc` 6 wrong to unclear; `native-kc-max` 8 right to unclear; `native-kc-max` 6 wrong to unclear; `native-kc-reach` 9 right to unclear; `native-kc-reach` 1 wrong to right; `native-kc-reach` 6 wrong to unclear; `native-shaped` 1 confident-wrong to wrong; `native-shaped` 5 right to unclear; `native-shaped` 2 unclear to declined; `native-shaped` 6 wrong to unclear).

Turns judged: 130 (126 the code left unclear, 4 confident-wrong with a hedge outside the list); verdicts that stood: 127.
Confident-wrong turns the judge moved: 0 of 4 (0 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `native-bare` `followup_how_computed` run 1 turn 2: wrong / right
- `native-kc-reach` `followup_how_computed` run 3 turn 2: wrong / right
- `native-shaped` `orders_over_100` run 3 turn 1: wrong / confident-wrong

### `google-data-agent (LATEST_GA_MODEL)`

Scored on all 3 runs of every case; runs finished: native-context-bare 228 of 228; model responses spent: native-context-bare 246.

| | `native-context-bare` |
|---|---|
| Accuracy | 97.4% |
| Confident-wrong | 2.6% |
| pass^3 | 96.1% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 100.0% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 86.7% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 13 (`native-context-bare` 7 right to unclear; `native-context-bare` 6 wrong to unclear).

Turns judged: 14 (13 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 14.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on all 3 runs of every case; runs finished: native-context-bare 228 of 228; model responses spent: native-context-bare 246.

| | `native-context-bare` |
|---|---|
| Accuracy | 98.7% |
| Confident-wrong | 1.3% |
| pass^3 | 98.7% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 100.0% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 93.3% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 15 (`native-context-bare` 9 right to unclear; `native-context-bare` 6 wrong to unclear).

Turns judged: 15 (15 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 15.

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on all 3 runs of every case; runs finished: native-context-bare 228 of 228; model responses spent: native-context-bare 246.

| | `native-context-bare` |
|---|---|
| Accuracy | 95.6% |
| Confident-wrong | 3.9% |
| pass^3 | 94.7% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 99.5% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 96.7% |
| `uncovered` (15) accuracy | 80.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 13 (`native-context-bare` 7 right to unclear; `native-context-bare` 6 wrong to unclear).

Turns judged: 13 (13 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 13.

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, accuracy 98.7%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.092 [-0.158, -0.039], confident-wrong -0.013 [-0.039, +0.000]: not worth building (decides; 76 runs finished).
- `custom-hybrid` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 42 of 76 cases: accuracy +0.000 [+0.000, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 42 runs finished).
- `custom-metricflow-compute` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.092 [-0.158, -0.039], confident-wrong -0.013 [-0.039, +0.000]: not worth building (decides; 76 runs finished).
- `custom-lightdash` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.395 [-0.500, -0.289], confident-wrong +0.066 [+0.000, +0.132]: not worth building (decides; 76 runs finished).
- `custom-toolbox` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.526 [-0.632, -0.421], confident-wrong +0.039 [-0.013, +0.092]: not worth building (decides; 76 runs finished).
- `native-mcp` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.053 [-0.105, -0.013], confident-wrong +0.026 [+0.000, +0.066]: not worth building (decides; 76 runs finished).
- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 75 of 76 cases: accuracy -0.084 [-0.151, -0.027], confident-wrong -0.013 [-0.040, +0.000]: not worth building (the check; 225 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.079 [-0.145, -0.026], confident-wrong -0.013 [-0.039, +0.000]: not worth building (the check; 76 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.474 [-0.592, -0.368], confident-wrong +0.000 [-0.039, +0.039]: not worth building (the check; 76 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.013 [-0.046, +0.026], confident-wrong -0.007 [-0.039, +0.020]: not worth building (the check; 152 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.154 [-0.237, -0.079], confident-wrong -0.013 [-0.039, +0.000]: not worth building (the check; 228 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.478 [-0.592, -0.368], confident-wrong +0.004 [-0.035, +0.044]: not worth building (the check; 228 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy +0.004 [-0.026, +0.039], confident-wrong -0.013 [-0.039, +0.000]: not worth building (the check; 228 runs finished).
- `custom-metricflow` (rung 4) on `claude-opus-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.184 [-0.276, -0.105], confident-wrong +0.000 [-0.033, +0.026]: not worth building (the check; 152 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.083 [-0.149, -0.026], confident-wrong -0.009 [-0.026, +0.000]: not worth building (the check; 228 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.101 [-0.167, -0.039], confident-wrong -0.009 [-0.039, +0.013]: not worth building (the check; 228 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.000 [-0.026, +0.035], confident-wrong -0.009 [-0.039, +0.013]: not worth building (the check; 228 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.079 [-0.140, -0.026], confident-wrong -0.013 [-0.039, +0.000]: not worth building (the check; 228 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.136 [-0.215, -0.066], confident-wrong -0.004 [-0.035, +0.018]: not worth building (the check; 228 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy +0.004 [+0.000, +0.013], confident-wrong -0.009 [-0.026, +0.000]: not worth building (the check; 228 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.237 [-0.329, -0.145], confident-wrong +0.013 [-0.026, +0.066]: not worth building (the check; 76 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.184 [-0.276, -0.105], confident-wrong +0.000 [-0.039, +0.039]: not worth building (the check; 76 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.184 [-0.276, -0.105], confident-wrong +0.000 [-0.039, +0.039]: not worth building (the check; 76 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.178 [-0.263, -0.099], confident-wrong +0.007 [-0.026, +0.039]: not worth building (the check; 152 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.191 [-0.276, -0.105], confident-wrong +0.000 [-0.033, +0.026]: not worth building (the check; 152 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 37 of 76 cases: accuracy -0.135 [-0.243, -0.027], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 37 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (subject-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.211 [-0.303, -0.118], confident-wrong +0.026 [-0.026, +0.079]: not worth building (the check; 76 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-hybrid`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow-compute`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-native-mcp`: the same verdict on every model, so the gap is not the model's.

## Every arm on the hard set

Written 2026-11-09T12:04Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl) and each live arm's `eval-hard-<arm>.jsonl` under [the rule](RULE.md): 40 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `claude -p (haiku)` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
141 of `baseline`'s 141 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `claude-haiku-5-5`

Scored on partial: 1 run(s) of 40 of 40 cases; runs finished: baseline 118 of 120, custom-metricflow 120 of 120, custom-hybrid 120 of 120, custom-toolbox 120 of 120, native-mcp 120 of 120; model responses spent: baseline 467, custom-metricflow 407, custom-hybrid 449, custom-toolbox 244, native-mcp 616.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 65.0% | 85.0% | 87.5% | 52.5% | 90.0% |
| Confident-wrong | 7.5% | 0.0% | 0.0% | 5.0% | 2.5% |
| pass^1 | 65.0% | 85.0% | 87.5% | 52.5% | 90.0% |
| `conversation` (7) accuracy | 57.1% | 85.7% | 85.7% | 42.9% | 71.4% |
| `covered` (21) accuracy | 71.4% | 95.2% | 90.5% | 71.4% | 85.7% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% | 80.0% | 100.0% |
| `uncovered` (19) accuracy | 57.9% | 73.7% | 84.2% | 31.6% | 94.7% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.200 [+0.050, +0.350]: a difference.
- Confident-wrong: -0.075 [-0.175, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 55 (`baseline` 3 confident-wrong to right; `baseline` 2 right to unclear; `baseline` 3 wrong to right; `custom-hybrid` 4 confident-wrong to right; `custom-hybrid` 4 right to unclear; `custom-hybrid` 3 wrong to right; `custom-metricflow` 8 confident-wrong to right; `custom-metricflow` 3 confident-wrong to wrong; `custom-metricflow` 5 right to unclear; `custom-metricflow` 4 wrong to right; `custom-toolbox` 3 right to unclear; `custom-toolbox` 3 wrong to right; `native-mcp` 4 confident-wrong to right; `native-mcp` 3 right to unclear; `native-mcp` 3 wrong to right).

Turns judged: 34 (18 the code left unclear, 16 confident-wrong with a hedge outside the list); verdicts that stood: 31.
Confident-wrong turns the judge moved: 13 of 16 (11 to wrong, hedged; 2 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_revenue_per_session` run 3 turn 1: right / wrong
- `custom-hybrid` `hard_mqls_social_september` run 1 turn 1: right / declined
- `custom-metricflow` `hard_weekend_vs_weekday` run 1 turn 1: right / right

### `claude-sonnet-5-5`

Scored on partial: 2 run(s) of 40 of 40 cases; runs finished: custom-metricflow 120 of 120, custom-toolbox 120 of 120, native-mcp 81 of 120; model responses spent: custom-metricflow 412, custom-toolbox 241, native-mcp 379.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 61.3% | 53.8% | 93.8% |
| Confident-wrong | 1.2% | 3.8% | 0.0% |
| pass^2 | 60.0% | 52.5% | 90.0% |
| `conversation` (7) accuracy | 85.7% | 57.1% | 78.6% |
| `covered` (21) accuracy | 90.5% | 73.8% | 88.1% |
| `trap` (5) accuracy | 100.0% | 80.0% | 100.0% |
| `uncovered` (19) accuracy | 28.9% | 31.6% | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 35 (`custom-metricflow` 1 confident-wrong to right; `custom-metricflow` 6 confident-wrong to wrong; `custom-metricflow` 5 right to unclear; `custom-metricflow` 6 wrong to right; `custom-toolbox` 6 right to unclear; `custom-toolbox` 3 wrong to right; `native-mcp` 5 right to unclear; `native-mcp` 3 wrong to right).

Turns judged: 29 (18 the code left unclear, 11 confident-wrong with a hedge outside the list); verdicts that stood: 27.
Confident-wrong turns the judge moved: 7 of 11 (5 to wrong, hedged; 2 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-toolbox` `hard_gmv_september` run 1 turn 1: confident-wrong / wrong
- `custom-toolbox` `hard_gmv_september` run 3 turn 1: confident-wrong / wrong

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 23 of 40 cases; runs finished: baseline 23 of 120, custom-metricflow 120 of 120, custom-hybrid 23 of 120, custom-lightdash 40 of 120, custom-toolbox 40 of 120, native-mcp 40 of 120; model responses spent: baseline 105, custom-metricflow 468, custom-hybrid 90, custom-lightdash 74, custom-toolbox 77, native-mcp 282.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-lightdash` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|---|
| Accuracy | 78.3% | 82.6% | 95.7% | 60.9% | 69.6% | 95.7% |
| Confident-wrong | 13.0% | 4.3% | 0.0% | 8.7% | 13.0% | 0.0% |
| pass^1 | 78.3% | 82.6% | 95.7% | 60.9% | 69.6% | 95.7% |
| `conversation` (5) accuracy | 40.0% | 60.0% | 80.0% | 40.0% | 40.0% | 80.0% |
| `covered` (16) accuracy | 75.0% | 81.2% | 93.8% | 56.2% | 68.8% | 93.8% |
| `trap` (4) accuracy | 75.0% | 100.0% | 100.0% | 75.0% | 50.0% | 100.0% |
| `uncovered` (7) accuracy | 85.7% | 85.7% | 100.0% | 71.4% | 71.4% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.043 [-0.174, +0.261]: no difference.
- Confident-wrong: -0.087 [-0.261, +0.087]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 17 (`baseline` 1 wrong to right; `custom-hybrid` 1 right to unclear; `custom-hybrid` 1 wrong to right; `custom-lightdash` 1 wrong to right; `custom-metricflow` 4 confident-wrong to right; `custom-metricflow` 4 right to unclear; `custom-metricflow` 1 wrong to right; `custom-toolbox` 1 right to unclear; `custom-toolbox` 1 wrong to right; `native-mcp` 1 right to unclear; `native-mcp` 1 wrong to right).

Turns judged: 20 (13 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 20.
Confident-wrong turns the judge moved: 4 of 7 (4 to wrong, hedged; 0 to unclear).

### `claude-code-strict (haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 120 of 120, cc-metricflow 120 of 120, cc-native-mcp 120 of 120; model responses spent: cc-metricflow-compute 132, cc-metricflow 132, cc-native-mcp 132.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 90.0% | 82.5% | 92.5% |
| Confident-wrong | 0.8% | 0.0% | 0.0% |
| pass^3 | 87.5% | 77.5% | 87.5% |
| `conversation` (7) accuracy | 100.0% | 100.0% | 66.7% |
| `covered` (21) accuracy | 100.0% | 98.4% | 88.9% |
| `trap` (5) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (19) accuracy | 78.9% | 64.9% | 96.5% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 11 (`cc-metricflow` 4 wrong to right; `cc-metricflow-compute` 4 wrong to right; `cc-native-mcp` 3 wrong to right).

Turns judged: 17 (15 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 16.
Confident-wrong turns the judge moved: 2 of 2 (1 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `cc-native-mcp` `hard_revenue_per_session` run 1 turn 1: right / right

### `claude-code-strict (sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 120 of 120, cc-metricflow 120 of 120, cc-native-mcp 120 of 120; model responses spent: cc-metricflow-compute 132, cc-metricflow 132, cc-native-mcp 132.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 85.0% | 65.8% | 92.5% |
| Confident-wrong | 1.7% | 0.0% | 0.0% |
| pass^3 | 82.5% | 57.5% | 90.0% |
| `conversation` (7) accuracy | 85.7% | 90.5% | 76.2% |
| `covered` (21) accuracy | 90.5% | 92.1% | 88.9% |
| `trap` (5) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (19) accuracy | 78.9% | 36.8% | 96.5% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 11 (`cc-metricflow` 6 wrong to right; `cc-metricflow-compute` 3 wrong to right; `cc-native-mcp` 2 wrong to right).

Turns judged: 11 (9 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 11.
Confident-wrong turns the judge moved: 2 of 2 (2 to wrong, hedged; 0 to unclear).

### `claude-code (haiku)`

Scored on partial: 1 run(s) of 40 of 40 cases; runs finished: cc-metricflow 40 of 120; model responses spent: cc-metricflow 44.

| | `cc-metricflow` |
|---|---|
| Accuracy | 45.0% |
| Confident-wrong | 7.5% |
| pass^1 | 45.0% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (21) accuracy | 85.7% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 8 (`cc-metricflow` 5 confident-wrong to wrong; `cc-metricflow` 2 unclear to declined; `cc-metricflow` 1 wrong to right).

Turns judged: 3 (3 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 3.

### `claude-code (sonnet)`

Scored on partial: 1 run(s) of 40 of 40 cases; runs finished: cc-metricflow 40 of 120; model responses spent: cc-metricflow 44.

| | `cc-metricflow` |
|---|---|
| Accuracy | 52.5% |
| Confident-wrong | 7.5% |
| pass^1 | 52.5% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (21) accuracy | 100.0% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 13 (`cc-metricflow` 10 confident-wrong to wrong; `cc-metricflow` 2 right to unclear; `cc-metricflow` 1 wrong to right).

Turns judged: 3 (3 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 3.

### `claude-code (opus)`

Scored on partial: 1 run(s) of 40 of 40 cases; runs finished: cc-metricflow 40 of 120; model responses spent: cc-metricflow 44.

| | `cc-metricflow` |
|---|---|
| Accuracy | 55.0% |
| Confident-wrong | 0.0% |
| pass^1 | 55.0% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (21) accuracy | 100.0% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 5.3% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 12 (`cc-metricflow` 11 confident-wrong to wrong; `cc-metricflow` 1 wrong to right).

### `claude-code (fresh-haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 120 of 120; model responses spent: cc-metricflow 132.

| | `cc-metricflow` |
|---|---|
| Accuracy | 60.0% |
| Confident-wrong | 2.5% |
| pass^3 | 50.0% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (21) accuracy | 93.7% |
| `trap` (5) accuracy | 93.3% |
| `uncovered` (19) accuracy | 22.8% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 14 (`cc-metricflow` 4 confident-wrong to right; `cc-metricflow` 2 confident-wrong to wrong; `cc-metricflow` 4 right to unclear; `cc-metricflow` 4 wrong to right).

Turns judged: 4 (4 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 4.

### `claude-code (fresh-sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 120 of 120; model responses spent: cc-metricflow 132.

| | `cc-metricflow` |
|---|---|
| Accuracy | 52.5% |
| Confident-wrong | 3.3% |
| pass^3 | 50.0% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (21) accuracy | 90.5% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 10.5% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 18 (`cc-metricflow` 12 confident-wrong to wrong; `cc-metricflow` 2 right to unclear; `cc-metricflow` 4 wrong to right).

Turns judged: 2 (2 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 2.

### `claude-code (fresh-opus)`

Scored on partial: 1 run(s) of 40 of 40 cases; runs finished: cc-metricflow 40 of 120; model responses spent: cc-metricflow 44.

| | `cc-metricflow` |
|---|---|
| Accuracy | 55.0% |
| Confident-wrong | 0.0% |
| pass^1 | 55.0% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (21) accuracy | 90.5% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 15.8% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 7 (`cc-metricflow` 4 confident-wrong to wrong; `cc-metricflow` 1 right to unclear; `cc-metricflow` 2 wrong to right).

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 40 of 40 cases; runs finished: native-bare 120 of 120, native-context-bare 120 of 120, native-context 120 of 120, native-governed 120 of 120, native-graph 120 of 120, native-kc-max 119 of 120, native-kc-reach 120 of 120, native-kc 120 of 120, native-shaped 120 of 120; model responses spent: native-bare 132, native-context-bare 132, native-context 133, native-governed 132, native-graph 132, native-kc-max 129, native-kc-reach 132, native-kc 132, native-shaped 132.

| | `native-bare` | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 60.0% | 95.0% | 95.0% | 75.0% | 62.5% | 92.5% | 85.0% | 70.0% | 67.5% |
| Confident-wrong | 35.0% | 0.0% | 0.0% | 0.0% | 20.0% | 2.5% | 10.0% | 15.0% | 15.0% |
| pass^1 | 60.0% | 95.0% | 95.0% | 75.0% | 62.5% | 92.5% | 85.0% | 70.0% | 67.5% |
| `conversation` (7) accuracy | 57.1% | 71.4% | 71.4% | 85.7% | 71.4% | 71.4% | 71.4% | 71.4% | 57.1% |
| `covered` (21) accuracy | 57.1% | 90.5% | 90.5% | 95.2% | 76.2% | 90.5% | 85.7% | 81.0% | 66.7% |
| `trap` (5) accuracy | 40.0% | 100.0% | 100.0% | 100.0% | 40.0% | 100.0% | 80.0% | 60.0% | 60.0% |
| `uncovered` (19) accuracy | 63.2% | 100.0% | 100.0% | 52.6% | 47.4% | 94.7% | 84.2% | 57.9% | 68.4% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 26 (`native-context` 3 wrong to right; `native-context-bare` 3 wrong to right; `native-governed` 3 wrong to right; `native-graph` 2 right to unclear; `native-graph` 3 wrong to right; `native-kc` 2 wrong to right; `native-kc-max` 4 wrong to right; `native-kc-reach` 3 wrong to right; `native-shaped` 3 wrong to right).

Turns judged: 15 (8 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 15.
Confident-wrong turns the judge moved: 2 of 7 (2 to wrong, hedged; 0 to unclear).

### `google-data-agent (LATEST_GA_MODEL)`

Scored on partial: 1 run(s) of 39 of 40 cases; runs finished: native-context-bare 119 of 120; model responses spent: native-context-bare 131.

| | `native-context-bare` |
|---|---|
| Accuracy | 97.4% |
| Confident-wrong | 2.6% |
| pass^1 | 97.4% |
| `conversation` (6) accuracy | 100.0% |
| `covered` (20) accuracy | 100.0% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 94.7% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 3 (`native-context-bare` 3 wrong to right).

Turns judged: 1 (0 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 1.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on partial: 2 run(s) of 40 of 40 cases; runs finished: native-context-bare 119 of 120; model responses spent: native-context-bare 131.

| | `native-context-bare` |
|---|---|
| Accuracy | 98.8% |
| Confident-wrong | 0.0% |
| pass^2 | 97.5% |
| `conversation` (7) accuracy | 92.9% |
| `covered` (21) accuracy | 97.6% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 3 (`native-context-bare` 3 wrong to right).

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on all 3 runs of every case; runs finished: native-context-bare 120 of 120; model responses spent: native-context-bare 132.

| | `native-context-bare` |
|---|---|
| Accuracy | 99.2% |
| Confident-wrong | 0.0% |
| pass^3 | 97.5% |
| `conversation` (7) accuracy | 95.2% |
| `covered` (21) accuracy | 98.4% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 3 (`native-context-bare` 3 wrong to right).

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, accuracy 99.2%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.150 [-0.267, -0.050], confident-wrong +0.008 [+0.000, +0.025]: not worth building (the check; 120 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.117 [-0.225, -0.025], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 120 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.483 [-0.633, -0.333], confident-wrong +0.042 [+0.000, +0.100]: not worth building (the check; 120 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.108 [-0.208, -0.033], confident-wrong +0.025 [+0.000, +0.058]: not worth building (the check; 120 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.367 [-0.517, -0.225], confident-wrong +0.008 [+0.000, +0.025]: not worth building (the check; 120 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.450 [-0.608, -0.300], confident-wrong +0.033 [+0.000, +0.092]: not worth building (the check; 120 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.054 [-0.121, -0.004], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 80 runs finished).
- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.208 [-0.333, -0.100], confident-wrong +0.033 [+0.000, +0.075]: not worth building (decides; 120 runs finished).
- `custom-hybrid` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 23 of 40 cases: accuracy -0.029 [-0.130, +0.043], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 23 runs finished).
- `custom-lightdash` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.592 [-0.742, -0.442], confident-wrong +0.100 [+0.025, +0.200]: not worth building (decides; 40 runs finished).
- `custom-toolbox` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.542 [-0.692, -0.392], confident-wrong +0.125 [+0.025, +0.225]: not worth building (decides; 40 runs finished).
- `native-mcp` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.017 [-0.075, +0.025], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 40 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.092 [-0.192, -0.008], confident-wrong +0.008 [+0.000, +0.025]: not worth building (the check; 120 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.167 [-0.283, -0.067], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 120 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.067 [-0.133, -0.017], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 120 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.142 [-0.250, -0.050], confident-wrong +0.017 [+0.000, +0.050]: not worth building (the check; 120 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.333 [-0.467, -0.200], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 120 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.067 [-0.142, -0.008], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 120 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.542 [-0.692, -0.392], confident-wrong +0.075 [+0.000, +0.175]: not worth building (the check; 40 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.467 [-0.625, -0.317], confident-wrong +0.075 [+0.000, +0.175]: not worth building (the check; 40 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.442 [-0.600, -0.292], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 40 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.392 [-0.533, -0.258], confident-wrong +0.025 [+0.000, +0.067]: not worth building (the check; 120 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.467 [-0.617, -0.325], confident-wrong +0.033 [+0.000, +0.083]: not worth building (the check; 120 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.442 [-0.592, -0.292], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 40 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-hybrid`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow-compute`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-native-mcp`: the same verdict on every model, so the gap is not the model's.

## Every arm on the hard set v2

Written 2026-11-09T12:04Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-v2-local.jsonl`](eval-hard-v2-local.jsonl) and each live arm's `eval-hard-v2-<arm>.jsonl` under [the rule](RULE.md): 54 cases of `services/semantic-agent/evals/semantic_bet_hard_v2.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `claude -p (haiku)` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
223 of `baseline`'s 223 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `claude-haiku-5-5`

Scored on partial: 1 run(s) of 40 of 54 cases; runs finished: baseline 118 of 162, custom-metricflow 120 of 162, custom-hybrid 120 of 162, custom-toolbox 120 of 162, native-mcp 120 of 162; model responses spent: baseline 467, custom-metricflow 407, custom-hybrid 449, custom-toolbox 244, native-mcp 616.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 65.0% | 82.5% | 90.0% | 52.5% | 90.0% |
| Confident-wrong | 7.5% | 0.0% | 0.0% | 5.0% | 2.5% |
| pass^1 | 65.0% | 82.5% | 90.0% | 52.5% | 90.0% |
| `composable` (14) accuracy | 71.4% | 85.7% | 100.0% | 42.9% | 92.9% |
| `conversation` (7) accuracy | 57.1% | 85.7% | 85.7% | 42.9% | 71.4% |
| `covered` (21) accuracy | 71.4% | 90.5% | 95.2% | 71.4% | 85.7% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% | 80.0% | 100.0% |
| `uncovered` (5) accuracy | 20.0% | 40.0% | 40.0% | 0.0% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.175 [+0.000, +0.350]: no difference.
- Confident-wrong: -0.075 [-0.175, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 55 (`baseline` 3 confident-wrong to right; `baseline` 2 right to unclear; `baseline` 3 wrong to right; `custom-hybrid` 4 confident-wrong to right; `custom-hybrid` 4 right to unclear; `custom-hybrid` 3 wrong to right; `custom-metricflow` 8 confident-wrong to right; `custom-metricflow` 3 confident-wrong to wrong; `custom-metricflow` 5 right to unclear; `custom-metricflow` 4 wrong to right; `custom-toolbox` 3 right to unclear; `custom-toolbox` 3 wrong to right; `native-mcp` 4 confident-wrong to right; `native-mcp` 3 right to unclear; `native-mcp` 3 wrong to right).

Turns judged: 34 (18 the code left unclear, 16 confident-wrong with a hedge outside the list); verdicts that stood: 31.
Confident-wrong turns the judge moved: 13 of 16 (11 to wrong, hedged; 2 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_basket_size_week` run 1 turn 1: confident-wrong / wrong
- `custom-metricflow` `hard_mqls_social_september` run 1 turn 1: declined / right
- `custom-metricflow` `hard_weekend_vs_weekday` run 1 turn 1: right / right

### `claude-sonnet-5-5`

Scored on partial: 1 run(s) of 40 of 54 cases; runs finished: custom-metricflow 120 of 162, custom-toolbox 120 of 162, native-mcp 81 of 162; model responses spent: custom-metricflow 412, custom-toolbox 241, native-mcp 379.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 60.0% | 55.0% | 95.0% |
| Confident-wrong | 2.5% | 5.0% | 0.0% |
| pass^1 | 60.0% | 55.0% | 95.0% |
| `composable` (14) accuracy | 28.6% | 42.9% | 100.0% |
| `conversation` (7) accuracy | 85.7% | 57.1% | 71.4% |
| `covered` (21) accuracy | 90.5% | 76.2% | 90.5% |
| `trap` (5) accuracy | 100.0% | 80.0% | 100.0% |
| `uncovered` (5) accuracy | 20.0% | 0.0% | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 35 (`custom-metricflow` 1 confident-wrong to right; `custom-metricflow` 6 confident-wrong to wrong; `custom-metricflow` 5 right to unclear; `custom-metricflow` 6 wrong to right; `custom-toolbox` 6 right to unclear; `custom-toolbox` 3 wrong to right; `native-mcp` 5 right to unclear; `native-mcp` 3 wrong to right).

Turns judged: 29 (18 the code left unclear, 11 confident-wrong with a hedge outside the list); verdicts that stood: 29.
Confident-wrong turns the judge moved: 6 of 11 (6 to wrong, hedged; 0 to unclear).

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 23 of 54 cases; runs finished: baseline 105 of 162, custom-metricflow 162 of 162, custom-hybrid 78 of 162, custom-metricflow-compute 162 of 162, custom-lightdash 40 of 162, custom-toolbox 40 of 162, native-mcp 54 of 162; model responses spent: baseline 516, custom-metricflow 616, custom-hybrid 304, custom-metricflow-compute 598, custom-lightdash 74, custom-toolbox 77, native-mcp 377.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-metricflow-compute` | `custom-lightdash` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|---|---|
| Accuracy | 78.3% | 82.6% | 95.7% | 95.7% | 60.9% | 69.6% | 95.7% |
| Confident-wrong | 13.0% | 4.3% | 0.0% | 0.0% | 8.7% | 13.0% | 0.0% |
| pass^1 | 78.3% | 82.6% | 95.7% | 95.7% | 60.9% | 69.6% | 95.7% |
| `composable` (7) accuracy | 85.7% | 85.7% | 100.0% | 100.0% | 71.4% | 71.4% | 100.0% |
| `conversation` (5) accuracy | 40.0% | 60.0% | 80.0% | 80.0% | 40.0% | 40.0% | 80.0% |
| `covered` (16) accuracy | 75.0% | 81.2% | 93.8% | 93.8% | 56.2% | 68.8% | 93.8% |
| `trap` (4) accuracy | 75.0% | 100.0% | 100.0% | 100.0% | 75.0% | 50.0% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.043 [-0.174, +0.261]: no difference.
- Confident-wrong: -0.087 [-0.261, +0.087]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 22 (`baseline` 1 wrong to right; `custom-hybrid` 1 right to unclear; `custom-hybrid` 3 wrong to right; `custom-lightdash` 1 wrong to right; `custom-metricflow` 4 confident-wrong to right; `custom-metricflow` 4 right to unclear; `custom-metricflow` 1 wrong to right; `custom-metricflow-compute` 3 wrong to right; `custom-toolbox` 1 right to unclear; `custom-toolbox` 1 wrong to right; `native-mcp` 1 right to unclear; `native-mcp` 1 wrong to right).

Turns judged: 29 (19 the code left unclear, 10 confident-wrong with a hedge outside the list); verdicts that stood: 29.
Confident-wrong turns the judge moved: 5 of 10 (5 to wrong, hedged; 0 to unclear).

### `claude-code-strict (haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 162 of 162, cc-metricflow 162 of 162, cc-native-mcp 162 of 162; model responses spent: cc-metricflow-compute 174, cc-metricflow 174, cc-native-mcp 174.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 79.6% | 72.8% | 95.1% |
| Confident-wrong | 3.7% | 3.7% | 1.2% |
| pass^3 | 77.8% | 70.4% | 92.6% |
| `composable` (21) accuracy | 88.9% | 73.0% | 100.0% |
| `conversation` (7) accuracy | 100.0% | 95.2% | 71.4% |
| `covered` (22) accuracy | 100.0% | 98.5% | 89.4% |
| `trap` (5) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (11) accuracy | 21.2% | 21.2% | 97.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 7 (`cc-metricflow` 3 wrong to right; `cc-metricflow-compute` 3 wrong to right; `cc-native-mcp` 1 wrong to right).

Turns judged: 19 (19 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 19.

### `claude-code-strict (sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 162 of 162, cc-metricflow 162 of 162, cc-native-mcp 162 of 162; model responses spent: cc-metricflow-compute 174, cc-metricflow 174, cc-native-mcp 174.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 80.2% | 64.8% | 94.4% |
| Confident-wrong | 6.2% | 4.9% | 0.6% |
| pass^3 | 77.8% | 59.3% | 90.7% |
| `composable` (21) accuracy | 90.5% | 55.6% | 96.8% |
| `conversation` (7) accuracy | 100.0% | 90.5% | 81.0% |
| `covered` (22) accuracy | 95.5% | 92.4% | 89.4% |
| `trap` (5) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (11) accuracy | 30.3% | 27.3% | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 15 (`cc-metricflow` 5 wrong to right; `cc-metricflow-compute` 5 wrong to right; `cc-native-mcp` 5 wrong to right).

Turns judged: 20 (14 the code left unclear, 6 confident-wrong with a hedge outside the list); verdicts that stood: 20.
Confident-wrong turns the judge moved: 4 of 6 (4 to wrong, hedged; 0 to unclear).

### `claude-code-strict (opus)`

Scored on partial: 1 run(s) of 34 of 54 cases; runs finished: cc-metricflow-compute 35 of 162, cc-metricflow 36 of 162, cc-native-mcp 49 of 162; model responses spent: cc-metricflow-compute 37, cc-metricflow 38, cc-native-mcp 53.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 79.4% | 50.0% | 91.2% |
| Confident-wrong | 0.0% | 5.9% | 0.0% |
| pass^1 | 79.4% | 50.0% | 91.2% |
| `composable` (11) accuracy | 90.9% | 0.0% | 81.8% |
| `conversation` (5) accuracy | 100.0% | 100.0% | 100.0% |
| `covered` (15) accuracy | 100.0% | 100.0% | 100.0% |
| `trap` (3) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (8) accuracy | 25.0% | 25.0% | 87.5% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 2 (`cc-metricflow` 1 wrong to right; `cc-native-mcp` 1 wrong to right).

Turns judged: 4 (4 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 4.

### `claude-code (haiku)`

Scored on partial: 1 run(s) of 54 of 54 cases; runs finished: cc-metricflow 54 of 162; model responses spent: cc-metricflow 58.

| | `cc-metricflow` |
|---|---|
| Accuracy | 35.2% |
| Confident-wrong | 13.0% |
| pass^1 | 35.2% |
| `composable` (21) accuracy | 0.0% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (22) accuracy | 86.4% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 8 (`cc-metricflow` 5 confident-wrong to wrong; `cc-metricflow` 2 unclear to declined; `cc-metricflow` 1 wrong to right).

Turns judged: 3 (3 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 3.

### `claude-code (sonnet)`

Scored on partial: 1 run(s) of 54 of 54 cases; runs finished: cc-metricflow 54 of 162; model responses spent: cc-metricflow 58.

| | `cc-metricflow` |
|---|---|
| Accuracy | 40.7% |
| Confident-wrong | 13.0% |
| pass^1 | 40.7% |
| `composable` (21) accuracy | 0.0% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (22) accuracy | 100.0% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 13 (`cc-metricflow` 10 confident-wrong to wrong; `cc-metricflow` 2 right to unclear; `cc-metricflow` 1 wrong to right).

Turns judged: 3 (3 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 3.

### `claude-code (opus)`

Scored on partial: 1 run(s) of 54 of 54 cases; runs finished: cc-metricflow 54 of 162; model responses spent: cc-metricflow 58.

| | `cc-metricflow` |
|---|---|
| Accuracy | 46.3% |
| Confident-wrong | 3.7% |
| pass^1 | 46.3% |
| `composable` (21) accuracy | 4.8% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (22) accuracy | 100.0% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 18.2% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 12 (`cc-metricflow` 11 confident-wrong to wrong; `cc-metricflow` 1 wrong to right).

### `claude-code (fresh-haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 162 of 162; model responses spent: cc-metricflow 174.

| | `cc-metricflow` |
|---|---|
| Accuracy | 50.6% |
| Confident-wrong | 5.6% |
| pass^3 | 40.7% |
| `composable` (21) accuracy | 28.6% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (22) accuracy | 93.9% |
| `trap` (5) accuracy | 93.3% |
| `uncovered` (11) accuracy | 6.1% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 14 (`cc-metricflow` 4 confident-wrong to right; `cc-metricflow` 2 confident-wrong to wrong; `cc-metricflow` 4 right to unclear; `cc-metricflow` 4 wrong to right).

Turns judged: 7 (4 the code left unclear, 3 confident-wrong with a hedge outside the list); verdicts that stood: 7.
Confident-wrong turns the judge moved: 3 of 3 (3 to wrong, hedged; 0 to unclear).

### `claude-code (fresh-sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 162 of 162; model responses spent: cc-metricflow 174.

| | `cc-metricflow` |
|---|---|
| Accuracy | 40.7% |
| Confident-wrong | 6.8% |
| pass^3 | 38.9% |
| `composable` (21) accuracy | 9.5% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (22) accuracy | 90.9% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 18 (`cc-metricflow` 12 confident-wrong to wrong; `cc-metricflow` 2 right to unclear; `cc-metricflow` 4 wrong to right).

Turns judged: 5 (2 the code left unclear, 3 confident-wrong with a hedge outside the list); verdicts that stood: 5.
Confident-wrong turns the judge moved: 3 of 3 (3 to wrong, hedged; 0 to unclear).

### `claude-code (fresh-opus)`

Scored on partial: 1 run(s) of 54 of 54 cases; runs finished: cc-metricflow 54 of 162; model responses spent: cc-metricflow 58.

| | `cc-metricflow` |
|---|---|
| Accuracy | 42.6% |
| Confident-wrong | 3.7% |
| pass^1 | 42.6% |
| `composable` (21) accuracy | 9.5% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (22) accuracy | 90.9% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 9.1% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 7 (`cc-metricflow` 4 confident-wrong to wrong; `cc-metricflow` 1 right to unclear; `cc-metricflow` 2 wrong to right).

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 40 of 54 cases; runs finished: native-bare 162 of 162, native-context-bare 120 of 162, native-context-python 54 of 162, native-context 162 of 162, native-governed 120 of 162, native-graph 120 of 162, native-kc-max 162 of 162, native-kc-reach 120 of 162, native-kc 120 of 162, native-shaped 120 of 162; model responses spent: native-bare 174, native-context-bare 132, native-context-python 58, native-context 175, native-governed 132, native-graph 132, native-kc-max 174, native-kc-reach 132, native-kc 132, native-shaped 132.

| | `native-bare` | `native-context-bare` | `native-context-python` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 60.0% | 95.0% | 97.5% | 95.0% | 75.0% | 62.5% | 92.5% | 85.0% | 70.0% | 67.5% |
| Confident-wrong | 35.0% | 0.0% | 0.0% | 0.0% | 0.0% | 20.0% | 2.5% | 10.0% | 15.0% | 15.0% |
| pass^1 | 60.0% | 95.0% | 97.5% | 95.0% | 75.0% | 62.5% | 92.5% | 85.0% | 70.0% | 67.5% |
| `composable` (14) accuracy | 64.3% | 100.0% | 100.0% | 100.0% | 71.4% | 42.9% | 92.9% | 85.7% | 50.0% | 64.3% |
| `conversation` (7) accuracy | 57.1% | 71.4% | 85.7% | 71.4% | 85.7% | 71.4% | 71.4% | 71.4% | 71.4% | 57.1% |
| `covered` (21) accuracy | 57.1% | 90.5% | 95.2% | 90.5% | 95.2% | 76.2% | 90.5% | 85.7% | 81.0% | 66.7% |
| `trap` (5) accuracy | 40.0% | 100.0% | 100.0% | 100.0% | 100.0% | 40.0% | 100.0% | 80.0% | 60.0% | 60.0% |
| `uncovered` (5) accuracy | 60.0% | 100.0% | 100.0% | 100.0% | 0.0% | 60.0% | 100.0% | 80.0% | 80.0% | 80.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 33 (`native-bare` 3 right to unclear; `native-context` 2 right to unclear; `native-context` 3 wrong to right; `native-context-bare` 3 wrong to right; `native-context-python` 1 wrong to right; `native-governed` 3 wrong to right; `native-graph` 2 right to unclear; `native-graph` 3 wrong to right; `native-kc` 2 wrong to right; `native-kc-max` 1 right to unclear; `native-kc-max` 4 wrong to right; `native-kc-reach` 3 wrong to right; `native-shaped` 3 wrong to right).

Turns judged: 22 (15 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 22.
Confident-wrong turns the judge moved: 2 of 7 (2 to wrong, hedged; 0 to unclear).

### `google-data-agent (LATEST_GA_MODEL)`

Scored on partial: 1 run(s) of 39 of 54 cases; runs finished: native-context-bare 119 of 162; model responses spent: native-context-bare 131.

| | `native-context-bare` |
|---|---|
| Accuracy | 97.4% |
| Confident-wrong | 2.6% |
| pass^1 | 97.4% |
| `composable` (14) accuracy | 92.9% |
| `conversation` (6) accuracy | 100.0% |
| `covered` (20) accuracy | 100.0% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (5) accuracy | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 3 (`native-context-bare` 3 wrong to right).

Turns judged: 1 (0 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 1.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on all 3 runs of every case; runs finished: native-context-bare 162 of 162; model responses spent: native-context-bare 174.

| | `native-context-bare` |
|---|---|
| Accuracy | 99.4% |
| Confident-wrong | 0.0% |
| pass^3 | 98.1% |
| `composable` (21) accuracy | 100.0% |
| `conversation` (7) accuracy | 95.2% |
| `covered` (22) accuracy | 98.5% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 6 (`native-context-bare` 3 right to unclear; `native-context-bare` 3 wrong to right).

Turns judged: 3 (3 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 3.

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on partial: 1 run(s) of 40 of 54 cases; runs finished: native-context-bare 120 of 162; model responses spent: native-context-bare 132.

| | `native-context-bare` |
|---|---|
| Accuracy | 100.0% |
| Confident-wrong | 0.0% |
| pass^1 | 100.0% |
| `composable` (14) accuracy | 100.0% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (21) accuracy | 100.0% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (5) accuracy | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 3 (`native-context-bare` 3 wrong to right).

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, accuracy 99.4%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 40 of 54 cases: accuracy -0.158 [-0.275, -0.058], confident-wrong +0.008 [+0.000, +0.025]: not worth building (the check; 120 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 40 of 54 cases: accuracy -0.108 [-0.217, -0.017], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 120 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 40 of 54 cases: accuracy -0.483 [-0.633, -0.333], confident-wrong +0.042 [+0.000, +0.100]: not worth building (the check; 120 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 40 of 54 cases: accuracy -0.108 [-0.208, -0.033], confident-wrong +0.025 [+0.000, +0.058]: not worth building (the check; 120 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 40 of 54 cases: accuracy -0.367 [-0.517, -0.225], confident-wrong +0.008 [+0.000, +0.025]: not worth building (the check; 120 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 40 of 54 cases: accuracy -0.450 [-0.608, -0.300], confident-wrong +0.042 [+0.000, +0.108]: not worth building (the check; 120 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 40 of 54 cases: accuracy -0.042 [-0.104, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 80 runs finished).
- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.278 [-0.389, -0.173], confident-wrong +0.056 [+0.012, +0.111]: not worth building (decides; 162 runs finished).
- `custom-hybrid` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 26 of 54 cases: accuracy -0.026 [-0.115, +0.038], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 78 runs finished).
- `custom-metricflow-compute` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.185 [-0.284, -0.093], confident-wrong +0.049 [+0.012, +0.099]: not worth building (decides; 162 runs finished).
- `custom-lightdash` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 40 of 54 cases: accuracy -0.592 [-0.742, -0.442], confident-wrong +0.100 [+0.025, +0.200]: not worth building (decides; 40 runs finished).
- `custom-toolbox` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 40 of 54 cases: accuracy -0.542 [-0.692, -0.392], confident-wrong +0.125 [+0.025, +0.225]: not worth building (decides; 40 runs finished).
- `native-mcp` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.012 [-0.056, +0.019], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 54 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.198 [-0.309, -0.099], confident-wrong +0.037 [+0.006, +0.086]: not worth building (the check; 162 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.265 [-0.389, -0.154], confident-wrong +0.037 [+0.006, +0.086]: not worth building (the check; 162 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.043 [-0.105, +0.000], confident-wrong +0.012 [+0.000, +0.031]: not worth building (the check; 162 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.191 [-0.296, -0.093], confident-wrong +0.062 [+0.012, +0.123]: not worth building (the check; 162 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.346 [-0.469, -0.228], confident-wrong +0.049 [+0.012, +0.099]: not worth building (the check; 162 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.049 [-0.111, -0.006], confident-wrong +0.006 [+0.000, +0.019]: not worth building (the check; 162 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 35 of 54 cases: accuracy -0.190 [-0.333, -0.067], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 35 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 36 of 54 cases: accuracy -0.519 [-0.685, -0.352], confident-wrong +0.056 [+0.000, +0.139]: not worth building (the check; 36 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 49 of 54 cases: accuracy -0.095 [-0.190, -0.020], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 49 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.642 [-0.765, -0.512], confident-wrong +0.130 [+0.056, +0.222]: not worth building (the check; 54 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.586 [-0.722, -0.451], confident-wrong +0.130 [+0.037, +0.222]: not worth building (the check; 54 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.531 [-0.667, -0.395], confident-wrong +0.037 [+0.000, +0.093]: not worth building (the check; 54 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.488 [-0.605, -0.370], confident-wrong +0.056 [+0.012, +0.111]: not worth building (the check; 162 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.586 [-0.710, -0.457], confident-wrong +0.068 [+0.019, +0.130]: not worth building (the check; 162 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.568 [-0.698, -0.438], confident-wrong +0.037 [+0.000, +0.093]: not worth building (the check; 54 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-hybrid`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow-compute`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-native-mcp`: the same verdict on every model, so the gap is not the model's.

### The rule on both sets

RULE.md § Changes since freezing (#356): each set goes through the rule on its own; an arm of ours is worth building only if step 2 holds on both sets, and where they disagree the cheaper rung wins, as a tie does.
- The managed best on the frozen set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 98.7%.
- The managed best on the hard set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 99.2%.
- `custom-metricflow` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-hybrid` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-metricflow-compute` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-lightdash` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-toolbox` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `native-mcp` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-metricflow` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-hybrid` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-toolbox` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `native-mcp` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-metricflow` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-toolbox` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `native-mcp` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-metricflow` on `claude-opus-5-5` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `cc-metricflow-compute` on `claude-code-strict (haiku)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code-strict (haiku)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-native-mcp` on `claude-code-strict (haiku)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow-compute` on `claude-code-strict (sonnet)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code-strict (sonnet)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-native-mcp` on `claude-code-strict (sonnet)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (haiku)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (sonnet)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (opus)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-haiku)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-sonnet)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-opus)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (subject-haiku)` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- Step 3 (RULE.md § The rule, 3; it applies when no arm of ours is worth building): the arms with no accuracy difference from the managed best on both sets: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)` (rung 1), `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)` (rung 1), `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)` (rung 1), `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)` (rung 1), `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)` (rung 1).
  The cheapest rung among them is 1: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)`, `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`; within a rung the arm with fewer moving parts named in its finding wins (§ The cost ladder), which the report names.
