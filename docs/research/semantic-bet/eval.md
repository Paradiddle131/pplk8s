# Every arm on the bet's sets

Each set is scored on its own under [the rule](RULE.md), with its own comparison against the managed best: [the frozen set](#every-arm-on-the-frozen-set), then [the hard set](#every-arm-on-the-hard-set), then [the hard set v2](#every-arm-on-the-hard-set-v2) (#356, #364).

## Every arm on the frozen set

Written 2026-11-10T01:46Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 74 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `claude -p (haiku)` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
110 of `baseline`'s 352 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 74 of 74 cases; runs finished: baseline 138 of 222, custom-metricflow 87 of 222, custom-hybrid 82 of 222, custom-metricflow-compute 92 of 222, custom-lightdash 74 of 222, custom-toolbox 74 of 222, native-mcp 74 of 222; model responses spent: baseline 550, custom-metricflow 337, custom-hybrid 330, custom-metricflow-compute 341, custom-lightdash 148, custom-toolbox 127, native-mcp 442.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-metricflow-compute` | `custom-lightdash` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|---|---|
| Accuracy | 89.2% | 91.9% | 98.6% | 91.9% | 60.8% | 47.3% | 94.6% |
| Confident-wrong | 5.4% | 0.0% | 1.4% | 0.0% | 8.1% | 5.4% | 2.7% |
| pass^1 | 89.2% | 91.9% | 98.6% | 91.9% | 60.8% | 47.3% | 94.6% |
| `conversation` (7) accuracy | 71.4% | 100.0% | 100.0% | 100.0% | 28.6% | 71.4% | 85.7% |
| `covered` (62) accuracy | 88.7% | 98.4% | 98.4% | 98.4% | 64.5% | 50.0% | 95.2% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 50.0% | 75.0% |
| `trap` (10) accuracy | 80.0% | 100.0% | 100.0% | 100.0% | 60.0% | 50.0% | 90.0% |
| `uncovered` (12) accuracy | 91.7% | 58.3% | 100.0% | 58.3% | 41.7% | 33.3% | 91.7% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.027 [-0.054, +0.108]: no difference.
- Confident-wrong: -0.054 [-0.108, -0.014]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 7 (`baseline` 2 wrong to unclear; `custom-lightdash` 1 unclear to declined; `custom-toolbox` 2 wrong to unclear; `native-mcp` 2 wrong to unclear).

Turns judged: 17 (11 the code left unclear, 6 confident-wrong with a hedge outside the list); verdicts that stood: 17.
Confident-wrong turns the judge moved: 4 of 6 (4 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `baseline` `bet_median_signup_to_first_order` run 1 turn 1: not judged yet
- `baseline` `planted_campaign_least_spend` run 2 turn 1: not judged yet
- `baseline` `planted_campaign_least_spend` run 3 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `baseline` `bet_sessions_per_order` run 3 turn 1: not judged yet
- `baseline` `median_order_value` run 3 turn 1: not judged yet

### `claude-haiku-5-5`

Scored on partial: 1 run(s) of 70 of 74 cases; runs finished: baseline 214 of 222, custom-metricflow 222 of 222, custom-hybrid 220 of 222, custom-toolbox 220 of 222, native-mcp 221 of 222; model responses spent: baseline 766, custom-metricflow 745, custom-hybrid 781, custom-toolbox 396, native-mcp 1044.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 68.6% | 91.4% | 92.9% | 55.7% | 100.0% |
| Confident-wrong | 2.9% | 0.0% | 0.0% | 1.4% | 0.0% |
| pass^1 | 68.6% | 91.4% | 92.9% | 55.7% | 100.0% |
| `conversation` (6) accuracy | 100.0% | 100.0% | 100.0% | 83.3% | 100.0% |
| `covered` (58) accuracy | 77.6% | 98.3% | 98.3% | 58.6% | 100.0% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% | 75.0% | 100.0% |
| `trap` (9) accuracy | 66.7% | 100.0% | 100.0% | 66.7% | 100.0% |
| `uncovered` (12) accuracy | 25.0% | 58.3% | 66.7% | 41.7% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.229 [+0.129, +0.329]: a difference.
- Confident-wrong: -0.029 [-0.071, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 76 (`baseline` 7 confident-wrong to right; `baseline` 2 right to unclear; `baseline` 6 wrong to unclear; `custom-hybrid` 9 confident-wrong to right; `custom-hybrid` 1 right to unclear; `custom-hybrid` 13 unclear to right; `custom-metricflow` 3 confident-wrong to right; `custom-metricflow` 1 confident-wrong to wrong; `custom-metricflow` 10 unclear to right; `custom-toolbox` 1 confident-wrong to right; `custom-toolbox` 6 wrong to unclear; `native-mcp` 7 confident-wrong to right; `native-mcp` 3 unclear to right; `native-mcp` 1 wrong to right; `native-mcp` 6 wrong to unclear).

Turns judged: 35 (21 the code left unclear, 14 confident-wrong with a hedge outside the list); verdicts that stood: 34.
Confident-wrong turns the judge moved: 12 of 14 (11 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `signups_september` run 1 turn 1: wrong / declined

### `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 222 of 222, custom-toolbox 222 of 222, native-mcp 222 of 222; model responses spent: custom-metricflow 724, custom-toolbox 388, native-mcp 985.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 85.6% | 52.3% | 99.1% |
| Confident-wrong | 0.0% | 1.8% | 0.0% |
| pass^3 | 83.8% | 51.4% | 98.6% |
| `conversation` (7) accuracy | 100.0% | 66.7% | 100.0% |
| `covered` (62) accuracy | 98.4% | 54.3% | 98.9% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 50.0% | 83.3% |
| `trap` (10) accuracy | 100.0% | 60.0% | 100.0% |
| `uncovered` (12) accuracy | 19.4% | 41.7% | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 26 (`custom-metricflow` 2 confident-wrong to right; `custom-metricflow` 1 confident-wrong to wrong; `custom-metricflow` 2 unclear to right; `custom-metricflow` 1 wrong to right; `custom-toolbox` 1 confident-wrong to right; `custom-toolbox` 5 wrong to unclear; `native-mcp` 7 right to unclear; `native-mcp` 1 unclear to right; `native-mcp` 6 wrong to unclear).

Turns judged: 25 (21 the code left unclear, 4 confident-wrong with a hedge outside the list); verdicts that stood: 25.
Confident-wrong turns the judge moved: 2 of 4 (2 to wrong, hedged; 0 to unclear).

### `claude-opus-5-5`

Scored on partial: 1 run(s) of 73 of 74 cases; runs finished: custom-metricflow 221 of 222; model responses spent: custom-metricflow 729.

| | `custom-metricflow` |
|---|---|
| Accuracy | 83.6% |
| Confident-wrong | 1.4% |
| pass^1 | 83.6% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (62) accuracy | 98.4% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (11) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 5 (`custom-metricflow` 4 right to unclear; `custom-metricflow` 1 unclear to right).

Turns judged: 4 (4 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 4.

### `claude-code-strict (haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 222 of 222, cc-metricflow 222 of 222, cc-native-mcp 222 of 222; model responses spent: cc-metricflow-compute 240, cc-metricflow 240, cc-native-mcp 240.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 91.9% | 91.0% | 98.6% |
| Confident-wrong | 0.0% | 0.5% | 0.5% |
| pass^3 | 91.9% | 89.2% | 95.9% |
| `conversation` (7) accuracy | 100.0% | 100.0% | 95.2% |
| `covered` (62) accuracy | 98.4% | 98.4% | 98.4% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 91.7% |
| `trap` (10) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (12) accuracy | 58.3% | 52.8% | 100.0% |

Turns judged: 21 (21 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 20.

Turns still unclear after judging (counted as wrong):

- `cc-metricflow-compute` `bet_cart_to_checkout_minutes` run 1 turn 1: declined / wrong

### `claude-code-strict (sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 222 of 222, cc-metricflow 222 of 222, cc-native-mcp 222 of 222; model responses spent: cc-metricflow-compute 240, cc-metricflow 240, cc-native-mcp 240.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 93.2% | 87.4% | 100.0% |
| Confident-wrong | 0.0% | 0.5% | 0.0% |
| pass^3 | 91.9% | 85.1% | 100.0% |
| `conversation` (7) accuracy | 100.0% | 100.0% | 100.0% |
| `covered` (62) accuracy | 98.4% | 97.8% | 100.0% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% |
| `trap` (10) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (12) accuracy | 66.7% | 33.3% | 100.0% |

Turns judged: 20 (20 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 20.

### `claude-code-strict (opus)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 222 of 222, cc-metricflow 222 of 222; model responses spent: cc-metricflow-compute 240, cc-metricflow 240.

| | `cc-metricflow-compute` | `cc-metricflow` |
|---|---|---|
| Accuracy | 94.6% | 82.9% |
| Confident-wrong | 0.0% | 0.0% |
| pass^3 | 94.6% | 82.4% |
| `conversation` (7) accuracy | 100.0% | 100.0% |
| `covered` (62) accuracy | 98.4% | 98.4% |
| `distractor` (1) accuracy | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% |
| `trap` (10) accuracy | 100.0% | 100.0% |
| `uncovered` (12) accuracy | 75.0% | 2.8% |

Turns judged: 16 (16 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 16.

### `claude-code (haiku)`

Scored on partial: 1 run(s) of 74 of 74 cases; runs finished: cc-metricflow 74 of 222; model responses spent: cc-metricflow 80.

| | `cc-metricflow` |
|---|---|
| Accuracy | 77.0% |
| Confident-wrong | 2.7% |
| pass^1 | 77.0% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (62) accuracy | 91.9% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 75.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (12) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 4 (`cc-metricflow` 1 confident-wrong to wrong; `cc-metricflow` 3 unclear to declined).

### `claude-code (sonnet)`

Scored on partial: 1 run(s) of 74 of 74 cases; runs finished: cc-metricflow 74 of 222; model responses spent: cc-metricflow 80.

| | `cc-metricflow` |
|---|---|
| Accuracy | 82.4% |
| Confident-wrong | 1.4% |
| pass^1 | 82.4% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (62) accuracy | 98.4% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (12) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 2 (`cc-metricflow` 1 unclear to declined; `cc-metricflow` 1 wrong to declined).

### `claude-code (opus)`

Scored on partial: 1 run(s) of 74 of 74 cases; runs finished: cc-metricflow 74 of 222; model responses spent: cc-metricflow 80.

| | `cc-metricflow` |
|---|---|
| Accuracy | 82.4% |
| Confident-wrong | 1.4% |
| pass^1 | 82.4% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (62) accuracy | 98.4% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (12) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 3 (`cc-metricflow` 2 confident-wrong to wrong; `cc-metricflow` 1 unclear to declined).

### `claude-code (fresh-haiku)`

Scored on partial: 1 run(s) of 74 of 74 cases; runs finished: cc-metricflow 221 of 222; model responses spent: cc-metricflow 239.

| | `cc-metricflow` |
|---|---|
| Accuracy | 83.8% |
| Confident-wrong | 1.4% |
| pass^1 | 83.8% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (62) accuracy | 96.8% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (12) accuracy | 16.7% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 4 (`cc-metricflow` 1 confident-wrong to right; `cc-metricflow` 2 confident-wrong to wrong; `cc-metricflow` 1 right to unclear).

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

### `claude-code (fresh-sonnet)`

Scored on partial: 1 run(s) of 74 of 74 cases; runs finished: cc-metricflow 221 of 222; model responses spent: cc-metricflow 239.

| | `cc-metricflow` |
|---|---|
| Accuracy | 82.4% |
| Confident-wrong | 1.4% |
| pass^1 | 82.4% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (62) accuracy | 96.8% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 75.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (12) accuracy | 8.3% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 3 (`cc-metricflow` 3 confident-wrong to wrong).

### `claude-code (fresh-opus)`

Scored on partial: 1 run(s) of 37 of 74 cases; runs finished: cc-metricflow 37 of 222; model responses spent: cc-metricflow 41.

| | `cc-metricflow` |
|---|---|
| Accuracy | 86.5% |
| Confident-wrong | 0.0% |
| pass^1 | 86.5% |
| `conversation` (4) accuracy | 100.0% |
| `covered` (33) accuracy | 97.0% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (2) accuracy | 100.0% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (4) accuracy | 0.0% |

### `claude-code (subject-haiku)`

Scored on partial: 1 run(s) of 74 of 74 cases; runs finished: cc-metricflow 74 of 222; model responses spent: cc-metricflow 80.

| | `cc-metricflow` |
|---|---|
| Accuracy | 79.7% |
| Confident-wrong | 4.1% |
| pass^1 | 79.7% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (62) accuracy | 93.5% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (12) accuracy | 8.3% |

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 73 of 74 cases; runs finished: native-bare 221 of 222, native-context-bare 222 of 222, native-context-python 74 of 222, native-context 222 of 222, native-governed 222 of 222, native-graph 222 of 222, native-kc-max 222 of 222, native-kc-reach 222 of 222, native-kc 222 of 222, native-shaped 222 of 222; model responses spent: native-bare 239, native-context-bare 240, native-context-python 80, native-context 240, native-governed 240, native-graph 240, native-kc-max 240, native-kc-reach 240, native-kc 240, native-shaped 240.

| | `native-bare` | `native-context-bare` | `native-context-python` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 78.1% | 97.3% | 98.6% | 95.9% | 84.9% | 68.5% | 93.2% | 89.0% | 72.6% | 69.9% |
| Confident-wrong | 20.5% | 2.7% | 1.4% | 2.7% | 1.4% | 8.2% | 6.8% | 8.2% | 4.1% | 5.5% |
| pass^1 | 78.1% | 97.3% | 98.6% | 95.9% | 84.9% | 68.5% | 93.2% | 89.0% | 72.6% | 69.9% |
| `conversation` (7) accuracy | 42.9% | 100.0% | 100.0% | 100.0% | 100.0% | 71.4% | 71.4% | 42.9% | 85.7% | 57.1% |
| `covered` (61) accuracy | 73.8% | 100.0% | 100.0% | 98.4% | 93.4% | 67.2% | 91.8% | 86.9% | 72.1% | 68.9% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 75.0% | 100.0% | 100.0% | 100.0% | 75.0% | 75.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `trap` (9) accuracy | 55.6% | 100.0% | 100.0% | 100.0% | 100.0% | 55.6% | 88.9% | 88.9% | 55.6% | 44.4% |
| `uncovered` (12) accuracy | 100.0% | 83.3% | 91.7% | 83.3% | 41.7% | 75.0% | 100.0% | 100.0% | 75.0% | 75.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 102 (`native-bare` 7 right to unclear; `native-bare` 6 wrong to unclear; `native-context` 6 right to unclear; `native-context` 6 wrong to unclear; `native-context-bare` 4 right to unclear; `native-context-bare` 6 wrong to unclear; `native-governed` 3 right to unclear; `native-governed` 6 wrong to unclear; `native-graph` 4 right to unclear; `native-graph` 1 wrong to right; `native-graph` 6 wrong to unclear; `native-kc` 3 right to unclear; `native-kc` 6 wrong to unclear; `native-kc-max` 5 right to unclear; `native-kc-max` 6 wrong to unclear; `native-kc-reach` 6 right to unclear; `native-kc-reach` 1 wrong to right; `native-kc-reach` 6 wrong to unclear; `native-shaped` 1 confident-wrong to wrong; `native-shaped` 5 right to unclear; `native-shaped` 2 unclear to declined; `native-shaped` 6 wrong to unclear).

Turns judged: 113 (109 the code left unclear, 4 confident-wrong with a hedge outside the list); verdicts that stood: 110.
Confident-wrong turns the judge moved: 0 of 4 (0 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `native-bare` `followup_how_computed` run 1 turn 2: wrong / right
- `native-kc-reach` `followup_how_computed` run 3 turn 2: wrong / right
- `native-shaped` `orders_over_100` run 3 turn 1: wrong / confident-wrong

### `google-data-agent (LATEST_GA_MODEL)`

Scored on all 3 runs of every case; runs finished: native-context-bare 222 of 222; model responses spent: native-context-bare 240.

| | `native-context-bare` |
|---|---|
| Accuracy | 98.6% |
| Confident-wrong | 1.4% |
| pass^3 | 97.3% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (62) accuracy | 100.0% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (12) accuracy | 91.7% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 10 (`native-context-bare` 4 right to unclear; `native-context-bare` 6 wrong to unclear).

Turns judged: 11 (10 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 11.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on all 3 runs of every case; runs finished: native-context-bare 222 of 222; model responses spent: native-context-bare 240.

| | `native-context-bare` |
|---|---|
| Accuracy | 100.0% |
| Confident-wrong | 0.0% |
| pass^3 | 100.0% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (62) accuracy | 100.0% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (12) accuracy | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 12 (`native-context-bare` 6 right to unclear; `native-context-bare` 6 wrong to unclear).

Turns judged: 12 (12 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 12.

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on all 3 runs of every case; runs finished: native-context-bare 222 of 222; model responses spent: native-context-bare 240.

| | `native-context-bare` |
|---|---|
| Accuracy | 96.8% |
| Confident-wrong | 2.7% |
| pass^3 | 95.9% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (62) accuracy | 99.5% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 96.7% |
| `uncovered` (12) accuracy | 83.3% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 10 (`native-context-bare` 4 right to unclear; `native-context-bare` 6 wrong to unclear).

Turns judged: 10 (10 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 10.

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, accuracy 100.0%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.081 [-0.149, -0.027], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 74 runs finished).
- `custom-hybrid` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.014 [-0.041, +0.000], confident-wrong +0.014 [+0.000, +0.041]: not worth building (decides; 74 runs finished).
- `custom-metricflow-compute` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.081 [-0.149, -0.027], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 74 runs finished).
- `custom-lightdash` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.392 [-0.500, -0.284], confident-wrong +0.081 [+0.027, +0.149]: not worth building (decides; 74 runs finished).
- `custom-toolbox` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.527 [-0.635, -0.419], confident-wrong +0.054 [+0.014, +0.108]: not worth building (decides; 74 runs finished).
- `native-mcp` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.054 [-0.108, -0.014], confident-wrong +0.027 [+0.000, +0.068]: not worth building (decides; 74 runs finished).
- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.086 [-0.153, -0.027], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 222 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.068 [-0.135, -0.014], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 74 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.473 [-0.581, -0.365], confident-wrong +0.014 [+0.000, +0.041]: not worth building (the check; 74 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.027 [-0.054, -0.007], confident-wrong +0.007 [+0.000, +0.020]: not worth building (the check; 148 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.144 [-0.225, -0.072], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 222 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.477 [-0.590, -0.365], confident-wrong +0.018 [+0.000, +0.050]: not worth building (the check; 222 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.009 [-0.027, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 222 runs finished).
- `custom-metricflow` (rung 4) on `claude-opus-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.176 [-0.270, -0.095], confident-wrong +0.014 [+0.000, +0.034]: not worth building (the check; 148 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.081 [-0.149, -0.027], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 222 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.090 [-0.158, -0.032], confident-wrong +0.005 [+0.000, +0.014]: not worth building (the check; 222 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.014 [-0.032, +0.000], confident-wrong +0.005 [+0.000, +0.014]: not worth building (the check; 222 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.068 [-0.126, -0.018], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 222 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.126 [-0.203, -0.059], confident-wrong +0.005 [+0.000, +0.014]: not worth building (the check; 222 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy +0.000 [+0.000, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 222 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.054 [-0.108, -0.014], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 222 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.171 [-0.261, -0.090], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 222 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.230 [-0.338, -0.135], confident-wrong +0.027 [+0.000, +0.068]: not worth building (the check; 74 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.176 [-0.270, -0.095], confident-wrong +0.014 [+0.000, +0.041]: not worth building (the check; 74 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.176 [-0.270, -0.095], confident-wrong +0.014 [+0.000, +0.041]: not worth building (the check; 74 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.169 [-0.257, -0.095], confident-wrong +0.020 [+0.000, +0.047]: not worth building (the check; 148 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.182 [-0.270, -0.101], confident-wrong +0.014 [+0.000, +0.034]: not worth building (the check; 148 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 37 of 74 cases: accuracy -0.135 [-0.243, -0.027], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 37 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (subject-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 74 of 74 cases: accuracy -0.203 [-0.297, -0.108], confident-wrong +0.041 [+0.000, +0.095]: not worth building (the check; 74 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-hybrid`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow-compute`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-native-mcp`: the same verdict on every model, so the gap is not the model's.

## Every arm on the hard set

Written 2026-11-10T01:46Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl) and each live arm's `eval-hard-<arm>.jsonl` under [the rule](RULE.md): 40 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
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

### `claude-code-strict (opus)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 120 of 120, cc-metricflow 120 of 120; model responses spent: cc-metricflow-compute 132, cc-metricflow 132.

| | `cc-metricflow-compute` | `cc-metricflow` |
|---|---|---|
| Accuracy | 92.5% | 59.2% |
| Confident-wrong | 0.0% | 0.8% |
| pass^3 | 92.5% | 52.5% |
| `conversation` (7) accuracy | 100.0% | 100.0% |
| `covered` (21) accuracy | 100.0% | 98.4% |
| `trap` (5) accuracy | 100.0% | 100.0% |
| `uncovered` (19) accuracy | 84.2% | 15.8% |

Turns judged: 12 (12 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 12.

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
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.067 [-0.158, +0.008], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 120 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`, 40 of 40 cases: accuracy -0.400 [-0.550, -0.258], confident-wrong +0.008 [+0.000, +0.025]: not worth building (the check; 120 runs finished).
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

Written 2026-11-10T01:46Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-v2-local.jsonl`](eval-hard-v2-local.jsonl) and each live arm's `eval-hard-v2-<arm>.jsonl` under [the rule](RULE.md): 54 cases of `services/semantic-agent/evals/semantic_bet_hard_v2.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `claude -p (haiku)` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
228 of `baseline`'s 228 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

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

Scored on partial: 1 run(s) of 40 of 54 cases; runs finished: baseline 110 of 162, custom-metricflow 162 of 162, custom-hybrid 162 of 162, custom-metricflow-compute 162 of 162, custom-lightdash 40 of 162, custom-toolbox 40 of 162, native-mcp 54 of 162; model responses spent: baseline 541, custom-metricflow 616, custom-hybrid 696, custom-metricflow-compute 598, custom-lightdash 74, custom-toolbox 77, native-mcp 377.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-metricflow-compute` | `custom-lightdash` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|---|---|
| Accuracy | 80.0% | 77.5% | 95.0% | 90.0% | 40.0% | 45.0% | 97.5% |
| Confident-wrong | 12.5% | 5.0% | 0.0% | 0.0% | 10.0% | 12.5% | 0.0% |
| pass^1 | 80.0% | 77.5% | 95.0% | 90.0% | 40.0% | 45.0% | 97.5% |
| `composable` (14) accuracy | 92.9% | 78.6% | 92.9% | 100.0% | 35.7% | 42.9% | 100.0% |
| `conversation` (7) accuracy | 42.9% | 71.4% | 85.7% | 85.7% | 28.6% | 28.6% | 85.7% |
| `covered` (21) accuracy | 71.4% | 85.7% | 95.2% | 95.2% | 47.6% | 57.1% | 95.2% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% | 100.0% | 60.0% | 40.0% | 100.0% |
| `uncovered` (5) accuracy | 80.0% | 40.0% | 100.0% | 40.0% | 20.0% | 0.0% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: -0.025 [-0.200, +0.150]: no difference.
- Confident-wrong: -0.075 [-0.200, +0.050]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 22 (`baseline` 1 wrong to right; `custom-hybrid` 1 right to unclear; `custom-hybrid` 3 wrong to right; `custom-lightdash` 1 wrong to right; `custom-metricflow` 4 confident-wrong to right; `custom-metricflow` 4 right to unclear; `custom-metricflow` 1 wrong to right; `custom-metricflow-compute` 3 wrong to right; `custom-toolbox` 1 right to unclear; `custom-toolbox` 1 wrong to right; `native-mcp` 1 right to unclear; `native-mcp` 1 wrong to right).

Turns judged: 32 (19 the code left unclear, 13 confident-wrong with a hedge outside the list); verdicts that stood: 32.
Confident-wrong turns the judge moved: 8 of 13 (8 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-hybrid` `hv2_median_gap_between_orders` run 3 turn 1: not judged yet
- `custom-hybrid` `hv2_signups_never_ordered` run 3 turn 1: not judged yet

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

Scored on partial: 1 run(s) of 49 of 54 cases; runs finished: cc-metricflow-compute 162 of 162, cc-metricflow 162 of 162, cc-native-mcp 49 of 162; model responses spent: cc-metricflow-compute 174, cc-metricflow 174, cc-native-mcp 53.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 85.7% | 49.0% | 89.8% |
| Confident-wrong | 0.0% | 4.1% | 0.0% |
| pass^1 | 85.7% | 49.0% | 89.8% |
| `composable` (19) accuracy | 94.7% | 5.3% | 84.2% |
| `conversation` (7) accuracy | 100.0% | 100.0% | 100.0% |
| `covered` (22) accuracy | 100.0% | 95.5% | 95.5% |
| `trap` (5) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (8) accuracy | 25.0% | 25.0% | 87.5% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 2 (`cc-metricflow` 1 wrong to right; `cc-native-mcp` 1 wrong to right).

Turns judged: 13 (12 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 13.
Confident-wrong turns the judge moved: 1 of 1 (1 to wrong, hedged; 0 to unclear).

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
- `custom-hybrid` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.080 [-0.154, -0.025], confident-wrong +0.037 [+0.000, +0.086]: not worth building (decides; 162 runs finished).
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
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.130 [-0.222, -0.049], confident-wrong +0.006 [+0.000, +0.019]: not worth building (the check; 162 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 54 of 54 cases: accuracy -0.525 [-0.654, -0.395], confident-wrong +0.019 [+0.000, +0.049]: not worth building (the check; 162 runs finished).
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
- The managed best on the frozen set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 100.0%.
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
- `cc-metricflow-compute` on `claude-code-strict (opus)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code-strict (opus)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (haiku)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (sonnet)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (opus)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-haiku)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-sonnet)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-opus)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (subject-haiku)` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- Step 3 (RULE.md § The rule, 3; it applies when no arm of ours is worth building): the arms with no accuracy difference from the managed best on both sets: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)` (rung 1), `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)` (rung 1), `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)` (rung 1), `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)` (rung 1).
  The cheapest rung among them is 1: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)`, `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`; within a rung the arm with fewer moving parts named in its finding wins (§ The cost ladder), which the report names.
