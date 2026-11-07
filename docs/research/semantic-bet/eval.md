# Every arm on the bet's sets

Each set is scored on its own under [the rule](RULE.md), with its own comparison against the managed best: [the frozen set](#every-arm-on-the-frozen-set), then [the hard set](#every-arm-on-the-hard-set), then [the hard set v2](#every-arm-on-the-hard-set-v2) (#356, #364).

## Every arm on the frozen set

Written 2026-11-07T09:16Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 76 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
34 of `baseline`'s 296 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 76 of 76 cases; runs finished: baseline 76 of 228, custom-metricflow 89 of 228, custom-hybrid 76 of 228, custom-lightdash 76 of 228, custom-toolbox 76 of 228, native-mcp 76 of 228; model responses spent: baseline 347, custom-metricflow 343, custom-hybrid 311, custom-lightdash 151, custom-toolbox 129, native-mcp 452.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-lightdash` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|---|
| Accuracy | 59.2% | 89.5% | 89.5% | 59.2% | 43.4% | 89.5% |
| Confident-wrong | 7.9% | 0.0% | 0.0% | 7.9% | 5.3% | 3.9% |
| pass^1 | 59.2% | 89.5% | 89.5% | 59.2% | 43.4% | 89.5% |
| `conversation` (7) accuracy | 42.9% | 100.0% | 100.0% | 28.6% | 42.9% | 57.1% |
| `covered` (61) accuracy | 68.9% | 100.0% | 100.0% | 65.6% | 47.5% | 91.8% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 50.0% | 75.0% |
| `trap` (10) accuracy | 60.0% | 100.0% | 100.0% | 60.0% | 50.0% | 90.0% |
| `uncovered` (15) accuracy | 20.0% | 46.7% | 46.7% | 33.3% | 26.7% | 80.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.303 [+0.197, +0.408]: a difference.
- Confident-wrong: -0.079 [-0.145, -0.026]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 9 (`baseline` 2 wrong to unclear; `custom-lightdash` 1 unclear to declined; `custom-metricflow` 1 unclear to declined; `custom-toolbox` 2 wrong to unclear; `native-mcp` 1 right to unclear; `native-mcp` 2 wrong to unclear).

Turns judged: 13 (6 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 13.
Confident-wrong turns the judge moved: 4 of 7 (4 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `customers_to_date` run 1 turn 1: not judged yet
- `baseline` `followup_how_computed` run 1 turn 2: not judged yet
- `baseline` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `custom-toolbox` `followup_how_computed` run 1 turn 2: not judged yet
- `custom-toolbox` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-mcp` `bet_peak_checkout_hour` run 1 turn 1: not judged yet
- `native-mcp` `followup_how_computed` run 1 turn 2: not judged yet
- `native-mcp` `followup_rate_how_computed` run 1 turn 2: not judged yet

### `claude-haiku-5-5`

Scored on partial: 1 run(s) of 71 of 76 cases; runs finished: baseline 220 of 228, custom-metricflow 225 of 228, custom-hybrid 225 of 228, custom-toolbox 226 of 228, native-mcp 227 of 228; model responses spent: baseline 785, custom-metricflow 753, custom-hybrid 805, custom-toolbox 402, native-mcp 1075.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 63.4% | 90.1% | 90.1% | 52.1% | 97.2% |
| Confident-wrong | 4.2% | 0.0% | 0.0% | 1.4% | 0.0% |
| pass^1 | 63.4% | 90.1% | 90.1% | 52.1% | 97.2% |
| `conversation` (6) accuracy | 66.7% | 100.0% | 100.0% | 50.0% | 66.7% |
| `covered` (57) accuracy | 73.7% | 100.0% | 100.0% | 56.1% | 96.5% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% | 75.0% | 100.0% |
| `trap` (9) accuracy | 66.7% | 100.0% | 100.0% | 66.7% | 100.0% |
| `uncovered` (14) accuracy | 21.4% | 50.0% | 50.0% | 35.7% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.268 [+0.169, +0.366]: a difference.
- Confident-wrong: -0.042 [-0.099, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 76 (`baseline` 7 confident-wrong to right; `baseline` 2 right to unclear; `baseline` 6 wrong to unclear; `custom-hybrid` 9 confident-wrong to right; `custom-hybrid` 1 right to unclear; `custom-hybrid` 13 unclear to right; `custom-metricflow` 3 confident-wrong to right; `custom-metricflow` 1 confident-wrong to wrong; `custom-metricflow` 10 unclear to right; `custom-toolbox` 1 confident-wrong to right; `custom-toolbox` 6 wrong to unclear; `native-mcp` 7 confident-wrong to right; `native-mcp` 3 unclear to right; `native-mcp` 1 wrong to right; `native-mcp` 6 wrong to unclear).

Turns judged: 11 (0 the code left unclear, 11 confident-wrong with a hedge outside the list); verdicts that stood: 9.
Confident-wrong turns the judge moved: 10 of 11 (8 to wrong, hedged; 2 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `damaged_returns` run 3 turn 1: wrong / declined
- `baseline` `followup_how_computed` run 1 turn 2: not judged yet
- `baseline` `followup_how_computed` run 2 turn 2: not judged yet
- `baseline` `followup_how_computed` run 3 turn 2: not judged yet
- `baseline` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `baseline` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `baseline` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `baseline` `returns_one_day` run 1 turn 1: not judged yet
- `baseline` `returns_one_day` run 2 turn 1: not judged yet
- `baseline` `shipped_orders` run 3 turn 1: declined / wrong
- `custom-hybrid` `bet_median_days_to_return` run 1 turn 1: not judged yet
- `custom-toolbox` `followup_how_computed` run 1 turn 2: not judged yet
- `custom-toolbox` `followup_how_computed` run 2 turn 2: not judged yet
- `custom-toolbox` `followup_how_computed` run 3 turn 2: not judged yet
- `custom-toolbox` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `custom-toolbox` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `custom-toolbox` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `native-mcp` `followup_how_computed` run 1 turn 2: not judged yet
- `native-mcp` `followup_how_computed` run 2 turn 2: not judged yet
- `native-mcp` `followup_how_computed` run 3 turn 2: not judged yet
- `native-mcp` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-mcp` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-mcp` `followup_rate_how_computed` run 3 turn 2: not judged yet

### `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 228 of 228, custom-toolbox 228 of 228, native-mcp 228 of 228; model responses spent: custom-metricflow 743, custom-toolbox 394, native-mcp 1016.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 83.3% | 48.7% | 93.4% |
| Confident-wrong | 0.0% | 1.8% | 0.0% |
| pass^3 | 81.6% | 48.7% | 92.1% |
| `conversation` (7) accuracy | 100.0% | 42.9% | 71.4% |
| `covered` (61) accuracy | 100.0% | 52.5% | 95.6% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 50.0% | 83.3% |
| `trap` (10) accuracy | 100.0% | 60.0% | 100.0% |
| `uncovered` (15) accuracy | 15.6% | 33.3% | 84.4% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 27 (`custom-metricflow` 2 confident-wrong to right; `custom-metricflow` 1 confident-wrong to wrong; `custom-metricflow` 1 unclear to declined; `custom-metricflow` 2 unclear to right; `custom-metricflow` 1 wrong to right; `custom-toolbox` 1 confident-wrong to right; `custom-toolbox` 5 wrong to unclear; `native-mcp` 7 right to unclear; `native-mcp` 1 unclear to right; `native-mcp` 6 wrong to unclear).

Turns judged: 9 (5 the code left unclear, 4 confident-wrong with a hedge outside the list); verdicts that stood: 9.
Confident-wrong turns the judge moved: 2 of 4 (2 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-toolbox` `followup_how_computed` run 1 turn 2: not judged yet
- `custom-toolbox` `followup_how_computed` run 3 turn 2: not judged yet
- `custom-toolbox` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `custom-toolbox` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `custom-toolbox` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `native-mcp` `bet_cart_to_checkout_minutes` run 1 turn 1: not judged yet
- `native-mcp` `bet_cart_to_checkout_minutes` run 3 turn 1: not judged yet
- `native-mcp` `bet_median_days_to_return` run 1 turn 1: not judged yet
- `native-mcp` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `native-mcp` `bet_median_days_to_return` run 3 turn 1: not judged yet
- `native-mcp` `bet_median_signup_to_first_order` run 1 turn 1: not judged yet
- `native-mcp` `bet_median_signup_to_first_order` run 3 turn 1: not judged yet
- `native-mcp` `followup_how_computed` run 1 turn 2: not judged yet
- `native-mcp` `followup_how_computed` run 2 turn 2: not judged yet
- `native-mcp` `followup_how_computed` run 3 turn 2: not judged yet
- `native-mcp` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-mcp` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-mcp` `followup_rate_how_computed` run 3 turn 2: not judged yet

### `claude-opus-5-5`

Scored on partial: 1 run(s) of 74 of 76 cases; runs finished: custom-metricflow 226 of 228; model responses spent: custom-metricflow 743.

| | `custom-metricflow` |
|---|---|
| Accuracy | 81.1% |
| Confident-wrong | 1.4% |
| pass^1 | 81.1% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 98.4% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (13) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 5 (`custom-metricflow` 4 right to unclear; `custom-metricflow` 1 unclear to right).

Turns judged: 2 (1 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 1 of 1 (1 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `calls_about_returns` run 1 turn 1: not judged yet
- `custom-metricflow` `calls_about_returns` run 2 turn 1: not judged yet
- `custom-metricflow` `calls_about_returns` run 3 turn 1: not judged yet
- `custom-metricflow` `cancelled_total` run 3 turn 1: not judged yet

### `claude-code-strict (haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 228 of 228, cc-metricflow 228 of 228, cc-native-mcp 228 of 228; model responses spent: cc-metricflow-compute 246, cc-metricflow 246, cc-native-mcp 246.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 87.3% | 87.3% | 97.4% |
| Confident-wrong | 1.8% | 1.3% | 0.4% |
| pass^3 | 86.8% | 82.9% | 94.7% |
| `conversation` (7) accuracy | 100.0% | 100.0% | 95.2% |
| `covered` (61) accuracy | 97.3% | 98.4% | 98.4% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% |
| `trap` (10) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (15) accuracy | 46.7% | 42.2% | 93.3% |

Turns judged: 15 (14 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 15.
Confident-wrong turns the judge moved: 1 of 1 (1 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `bet_cart_to_checkout_minutes` run 3 turn 1: not judged yet
- `cc-metricflow-compute` `bet_cart_to_checkout_minutes` run 1 turn 1: not judged yet
- `cc-metricflow-compute` `bet_cart_to_checkout_minutes` run 2 turn 1: not judged yet
- `cc-metricflow-compute` `bet_cart_to_checkout_minutes` run 3 turn 1: not judged yet
- `cc-metricflow-compute` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `cc-metricflow-compute` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `cc-metricflow-compute` `page_views_one_day` run 2 turn 1: not judged yet
- `cc-metricflow-compute` `page_views_one_day` run 3 turn 1: not judged yet
- `cc-native-mcp` `bet_peak_checkout_hour` run 1 turn 1: not judged yet
- `cc-native-mcp` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `cc-native-mcp` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `cc-native-mcp` `page_views_one_day` run 3 turn 1: not judged yet

### `claude-code-strict (sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 228 of 228, cc-metricflow 228 of 228, cc-native-mcp 228 of 228; model responses spent: cc-metricflow-compute 246, cc-metricflow 246, cc-native-mcp 246.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 87.3% | 80.3% | 96.1% |
| Confident-wrong | 0.0% | 3.5% | 0.9% |
| pass^3 | 84.2% | 75.0% | 93.4% |
| `conversation` (7) accuracy | 100.0% | 100.0% | 100.0% |
| `covered` (61) accuracy | 96.7% | 93.4% | 100.0% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% |
| `trap` (10) accuracy | 100.0% | 96.7% | 100.0% |
| `uncovered` (15) accuracy | 48.9% | 26.7% | 80.0% |

Turns judged: 23 (21 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 23.
Confident-wrong turns the judge moved: 2 of 2 (2 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `page_views_one_day` run 3 turn 1: not judged yet
- `cc-metricflow-compute` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `cc-native-mcp` `bet_cart_to_checkout_minutes` run 2 turn 1: not judged yet
- `cc-native-mcp` `bet_median_days_to_return` run 1 turn 1: not judged yet
- `cc-native-mcp` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `cc-native-mcp` `bet_median_days_to_return` run 3 turn 1: not judged yet
- `cc-native-mcp` `bet_median_signup_to_first_order` run 2 turn 1: not judged yet
- `cc-native-mcp` `bet_peak_checkout_hour` run 1 turn 1: not judged yet
- `cc-native-mcp` `bet_peak_checkout_hour` run 3 turn 1: not judged yet

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
| Accuracy | 80.3% |
| Confident-wrong | 1.3% |
| pass^1 | 80.3% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (61) accuracy | 96.7% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 13.3% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 4 (`cc-metricflow` 1 confident-wrong to right; `cc-metricflow` 2 confident-wrong to wrong; `cc-metricflow` 1 right to unclear).

Turns judged: 2 (2 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 2.

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `page_views_one_day` run 1 turn 1: not judged yet

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

Scored on partial: 1 run(s) of 75 of 76 cases; runs finished: native-bare 227 of 228, native-context-bare 228 of 228, native-context 228 of 228, native-governed 228 of 228, native-graph 228 of 228, native-kc-max 228 of 228, native-kc-reach 228 of 228, native-kc 228 of 228, native-shaped 228 of 228; model responses spent: native-bare 245, native-context-bare 246, native-context 246, native-governed 246, native-graph 246, native-kc-max 246, native-kc-reach 246, native-kc 246, native-shaped 246.

| | `native-bare` | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 73.3% | 90.7% | 89.3% | 78.7% | 64.0% | 85.3% | 84.0% | 68.0% | 62.7% |
| Confident-wrong | 20.0% | 4.0% | 4.0% | 1.3% | 9.3% | 6.7% | 8.0% | 5.3% | 6.7% |
| pass^1 | 73.3% | 90.7% | 89.3% | 78.7% | 64.0% | 85.3% | 84.0% | 68.0% | 62.7% |
| `conversation` (7) accuracy | 28.6% | 71.4% | 71.4% | 71.4% | 42.9% | 42.9% | 28.6% | 57.1% | 28.6% |
| `covered` (60) accuracy | 71.7% | 95.0% | 95.0% | 88.3% | 65.0% | 86.7% | 85.0% | 70.0% | 63.3% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 75.0% | 100.0% | 100.0% | 75.0% | 75.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `trap` (9) accuracy | 55.6% | 100.0% | 100.0% | 100.0% | 55.6% | 88.9% | 88.9% | 55.6% | 44.4% |
| `uncovered` (15) accuracy | 80.0% | 73.3% | 66.7% | 40.0% | 60.0% | 80.0% | 80.0% | 60.0% | 60.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 116 (`native-bare` 10 right to unclear; `native-bare` 6 wrong to unclear; `native-context` 9 right to unclear; `native-context` 6 wrong to unclear; `native-context-bare` 7 right to unclear; `native-context-bare` 6 wrong to unclear; `native-governed` 4 right to unclear; `native-governed` 6 wrong to unclear; `native-graph` 4 right to unclear; `native-graph` 6 wrong to unclear; `native-kc` 3 right to unclear; `native-kc` 6 wrong to unclear; `native-kc-max` 8 right to unclear; `native-kc-max` 6 wrong to unclear; `native-kc-reach` 9 right to unclear; `native-kc-reach` 6 wrong to unclear; `native-shaped` 1 confident-wrong to wrong; `native-shaped` 5 right to unclear; `native-shaped` 2 unclear to declined; `native-shaped` 6 wrong to unclear).

Turns judged: 12 (8 the code left unclear, 4 confident-wrong with a hedge outside the list); verdicts that stood: 12.
Confident-wrong turns the judge moved: 1 of 4 (1 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `native-bare` `bet_median_days_to_return` run 1 turn 1: not judged yet
- `native-bare` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `native-bare` `bet_median_days_to_return` run 3 turn 1: not judged yet
- `native-bare` `bet_median_signup_to_first_order` run 2 turn 1: not judged yet
- `native-bare` `bet_median_signup_to_first_order` run 3 turn 1: not judged yet
- `native-bare` `bet_peak_checkout_hour` run 1 turn 1: not judged yet
- `native-bare` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `native-bare` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `native-bare` `engaged_customers_week` run 1 turn 1: not judged yet
- `native-bare` `engaged_customers_week` run 3 turn 1: not judged yet
- `native-bare` `followup_how_computed` run 1 turn 2: not judged yet
- `native-bare` `followup_how_computed` run 2 turn 2: not judged yet
- `native-bare` `followup_how_computed` run 3 turn 2: not judged yet
- `native-bare` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-bare` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-bare` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `native-context` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `native-context` `bet_median_days_to_return` run 3 turn 1: not judged yet
- `native-context` `bet_median_signup_to_first_order` run 1 turn 1: not judged yet
- `native-context` `bet_median_signup_to_first_order` run 3 turn 1: not judged yet
- `native-context` `bet_peak_checkout_hour` run 1 turn 1: not judged yet
- `native-context` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `native-context` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `native-context` `engaged_customers_week` run 2 turn 1: not judged yet
- `native-context` `engaged_customers_week` run 3 turn 1: not judged yet
- `native-context` `followup_how_computed` run 1 turn 2: not judged yet
- `native-context` `followup_how_computed` run 2 turn 2: not judged yet
- `native-context` `followup_how_computed` run 3 turn 2: not judged yet
- `native-context` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-context` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-context` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `native-context-bare` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `native-context-bare` `bet_median_days_to_return` run 3 turn 1: not judged yet
- `native-context-bare` `bet_median_signup_to_first_order` run 3 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 1 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `native-context-bare` `engaged_customers_week` run 1 turn 1: not judged yet
- `native-context-bare` `followup_how_computed` run 1 turn 2: not judged yet
- `native-context-bare` `followup_how_computed` run 2 turn 2: not judged yet
- `native-context-bare` `followup_how_computed` run 3 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `native-governed` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `native-governed` `engaged_customers_week` run 1 turn 1: not judged yet
- `native-governed` `engaged_customers_week` run 2 turn 1: not judged yet
- `native-governed` `engaged_customers_week` run 3 turn 1: not judged yet
- `native-governed` `followup_how_computed` run 1 turn 2: not judged yet
- `native-governed` `followup_how_computed` run 2 turn 2: not judged yet
- `native-governed` `followup_how_computed` run 3 turn 2: not judged yet
- `native-governed` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-governed` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-governed` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `native-graph` `active_customers` run 2 turn 1: not judged yet
- `native-graph` `bet_median_days_to_return` run 1 turn 1: not judged yet
- `native-graph` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `native-graph` `bet_median_days_to_return` run 3 turn 1: not judged yet
- `native-graph` `followup_how_computed` run 1 turn 2: not judged yet
- `native-graph` `followup_how_computed` run 2 turn 2: not judged yet
- `native-graph` `followup_how_computed` run 3 turn 2: not judged yet
- `native-graph` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-graph` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-graph` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `native-kc` `bet_median_days_to_return` run 1 turn 1: not judged yet
- `native-kc` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `native-kc` `bet_median_days_to_return` run 3 turn 1: not judged yet
- `native-kc` `followup_how_computed` run 1 turn 2: not judged yet
- `native-kc` `followup_how_computed` run 2 turn 2: not judged yet
- `native-kc` `followup_how_computed` run 3 turn 2: not judged yet
- `native-kc` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-kc` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-kc` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `native-kc-max` `bet_median_days_to_return` run 1 turn 1: not judged yet
- `native-kc-max` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `native-kc-max` `bet_median_signup_to_first_order` run 1 turn 1: not judged yet
- `native-kc-max` `bet_peak_checkout_hour` run 1 turn 1: not judged yet
- `native-kc-max` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `native-kc-max` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `native-kc-max` `engaged_customers_week` run 1 turn 1: not judged yet
- `native-kc-max` `engaged_customers_week` run 2 turn 1: not judged yet
- `native-kc-max` `followup_how_computed` run 1 turn 2: not judged yet
- `native-kc-max` `followup_how_computed` run 2 turn 2: not judged yet
- `native-kc-max` `followup_how_computed` run 3 turn 2: not judged yet
- `native-kc-max` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-kc-max` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-kc-max` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `native-kc-reach` `bet_median_days_to_return` run 1 turn 1: not judged yet
- `native-kc-reach` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `native-kc-reach` `bet_median_days_to_return` run 3 turn 1: not judged yet
- `native-kc-reach` `bet_peak_checkout_hour` run 1 turn 1: not judged yet
- `native-kc-reach` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `native-kc-reach` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `native-kc-reach` `engaged_customers_week` run 1 turn 1: not judged yet
- `native-kc-reach` `engaged_customers_week` run 2 turn 1: not judged yet
- `native-kc-reach` `engaged_customers_week` run 3 turn 1: not judged yet
- `native-kc-reach` `followup_how_computed` run 1 turn 2: not judged yet
- `native-kc-reach` `followup_how_computed` run 2 turn 2: not judged yet
- `native-kc-reach` `followup_how_computed` run 3 turn 2: not judged yet
- `native-kc-reach` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-kc-reach` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-kc-reach` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `native-shaped` `bet_median_days_to_return` run 1 turn 1: not judged yet
- `native-shaped` `bet_median_days_to_return` run 3 turn 1: not judged yet
- `native-shaped` `bet_median_signup_to_first_order` run 1 turn 1: not judged yet
- `native-shaped` `followup_how_computed` run 1 turn 2: not judged yet
- `native-shaped` `followup_how_computed` run 2 turn 2: not judged yet
- `native-shaped` `followup_how_computed` run 3 turn 2: not judged yet
- `native-shaped` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-shaped` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-shaped` `followup_rate_how_computed` run 3 turn 2: not judged yet
- `native-shaped` `orders_over_100` run 1 turn 1: not judged yet
- `native-shaped` `orders_over_100` run 3 turn 1: not judged yet

### `google-data-agent (LATEST_GA_MODEL)`

Scored on all 3 runs of every case; runs finished: native-context-bare 228 of 228; model responses spent: native-context-bare 246.

| | `native-context-bare` |
|---|---|
| Accuracy | 91.7% |
| Confident-wrong | 2.6% |
| pass^3 | 89.5% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (61) accuracy | 96.2% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 73.3% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 13 (`native-context-bare` 7 right to unclear; `native-context-bare` 6 wrong to unclear).

Turns judged: 1 (0 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 1.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `native-context-bare` `bet_cart_to_checkout_minutes` run 1 turn 1: not judged yet
- `native-context-bare` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `native-context-bare` `bet_median_days_to_return` run 3 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 1 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `native-context-bare` `engaged_customers_week` run 1 turn 1: not judged yet
- `native-context-bare` `followup_how_computed` run 1 turn 2: not judged yet
- `native-context-bare` `followup_how_computed` run 2 turn 2: not judged yet
- `native-context-bare` `followup_how_computed` run 3 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 3 turn 2: not judged yet

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on all 3 runs of every case; runs finished: native-context-bare 228 of 228; model responses spent: native-context-bare 246.

| | `native-context-bare` |
|---|---|
| Accuracy | 92.1% |
| Confident-wrong | 1.3% |
| pass^3 | 90.8% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (61) accuracy | 95.1% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 80.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 15 (`native-context-bare` 9 right to unclear; `native-context-bare` 6 wrong to unclear).

Turns still unclear after judging (counted as wrong):

- `native-context-bare` `bet_cart_to_checkout_minutes` run 2 turn 1: not judged yet
- `native-context-bare` `bet_cart_to_checkout_minutes` run 3 turn 1: not judged yet
- `native-context-bare` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 1 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `native-context-bare` `engaged_customers_week` run 1 turn 1: not judged yet
- `native-context-bare` `engaged_customers_week` run 2 turn 1: not judged yet
- `native-context-bare` `engaged_customers_week` run 3 turn 1: not judged yet
- `native-context-bare` `followup_how_computed` run 1 turn 2: not judged yet
- `native-context-bare` `followup_how_computed` run 2 turn 2: not judged yet
- `native-context-bare` `followup_how_computed` run 3 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 3 turn 2: not judged yet

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on all 3 runs of every case; runs finished: native-context-bare 228 of 228; model responses spent: native-context-bare 246.

| | `native-context-bare` |
|---|---|
| Accuracy | 89.9% |
| Confident-wrong | 3.9% |
| pass^3 | 86.8% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (61) accuracy | 95.6% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 96.7% |
| `uncovered` (15) accuracy | 66.7% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 13 (`native-context-bare` 7 right to unclear; `native-context-bare` 6 wrong to unclear).

Turns still unclear after judging (counted as wrong):

- `native-context-bare` `bet_median_days_to_return` run 1 turn 1: not judged yet
- `native-context-bare` `bet_median_days_to_return` run 2 turn 1: not judged yet
- `native-context-bare` `bet_median_signup_to_first_order` run 3 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 1 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `native-context-bare` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `native-context-bare` `engaged_customers_week` run 2 turn 1: not judged yet
- `native-context-bare` `followup_how_computed` run 1 turn 2: not judged yet
- `native-context-bare` `followup_how_computed` run 2 turn 2: not judged yet
- `native-context-bare` `followup_how_computed` run 3 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 1 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 2 turn 2: not judged yet
- `native-context-bare` `followup_rate_how_computed` run 3 turn 2: not judged yet

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, accuracy 92.1%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.026 [-0.096, +0.044], confident-wrong -0.013 [-0.039, +0.000]: not worth building (decides; 89 runs finished).
- `custom-hybrid` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.026 [-0.096, +0.044], confident-wrong -0.013 [-0.039, +0.000]: not worth building (decides; 76 runs finished).
- `custom-lightdash` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.329 [-0.443, -0.211], confident-wrong +0.066 [+0.000, +0.132]: not worth building (decides; 76 runs finished).
- `custom-toolbox` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.487 [-0.601, -0.377], confident-wrong +0.039 [-0.013, +0.092]: not worth building (decides; 76 runs finished).
- `native-mcp` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.026 [-0.092, +0.035], confident-wrong +0.026 [+0.000, +0.066]: not worth building (decides; 76 runs finished).
- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 75 of 76 cases: accuracy -0.031 [-0.107, +0.040], confident-wrong -0.013 [-0.040, +0.000]: not worth building (the check; 225 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.026 [-0.096, +0.044], confident-wrong -0.013 [-0.039, +0.000]: not worth building (the check; 225 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.421 [-0.531, -0.316], confident-wrong +0.009 [-0.031, +0.044]: not worth building (the check; 226 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy +0.031 [-0.018, +0.088], confident-wrong -0.009 [-0.039, +0.013]: not worth building (the check; 227 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.088 [-0.171, -0.004], confident-wrong -0.013 [-0.039, +0.000]: not worth building (the check; 228 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.434 [-0.544, -0.329], confident-wrong +0.004 [-0.035, +0.044]: not worth building (the check; 228 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy +0.013 [-0.035, +0.070], confident-wrong -0.013 [-0.039, +0.000]: not worth building (the check; 228 runs finished).
- `custom-metricflow` (rung 4) on `claude-opus-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.136 [-0.232, -0.039], confident-wrong -0.004 [-0.035, +0.018]: not worth building (the check; 226 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.048 [-0.127, +0.026], confident-wrong +0.004 [-0.026, +0.039]: not worth building (the check; 228 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.048 [-0.118, +0.026], confident-wrong -0.000 [-0.035, +0.026]: not worth building (the check; 228 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy +0.053 [+0.004, +0.114], confident-wrong -0.009 [-0.039, +0.013]: worth building (the check; 228 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.048 [-0.123, +0.026], confident-wrong -0.013 [-0.039, +0.000]: not worth building (the check; 228 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.118 [-0.206, -0.031], confident-wrong +0.022 [-0.022, +0.066]: not worth building (the check; 228 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy +0.039 [-0.004, +0.092], confident-wrong -0.004 [-0.013, +0.000]: not worth building (the check; 228 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.171 [-0.276, -0.066], confident-wrong +0.013 [-0.026, +0.066]: not worth building (the check; 76 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.118 [-0.211, -0.026], confident-wrong +0.000 [-0.039, +0.039]: not worth building (the check; 76 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.118 [-0.211, -0.026], confident-wrong +0.000 [-0.039, +0.039]: not worth building (the check; 76 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.125 [-0.215, -0.033], confident-wrong +0.013 [-0.022, +0.048]: not worth building (the check; 226 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.123 [-0.215, -0.031], confident-wrong -0.004 [-0.035, +0.018]: not worth building (the check; 227 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 37 of 76 cases: accuracy -0.108 [-0.243, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 37 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (subject-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 76 of 76 cases: accuracy -0.145 [-0.241, -0.048], confident-wrong +0.026 [-0.026, +0.079]: not worth building (the check; 76 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-hybrid`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow-compute`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-native-mcp`: the verdict moves with the model, so the gap is at least partly the model's.

### Errors

- No answer: the model call failed (litellm.APIError: APIError: OpenrouterException - Response payload is not completed: <TransferEncodingError: 400, message='Not enough data to satisfy transfer length header.'> LiteLLM Retried: 2 times).

## Every arm on the hard set

Written 2026-11-07T09:17Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl) and each live arm's `eval-hard-<arm>.jsonl` under [the rule](RULE.md): 41 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
162 of `baseline`'s 162 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `claude-haiku-5-5`

Scored on partial: 1 run(s) of 41 of 41 cases; runs finished: baseline 121 of 123, custom-metricflow 123 of 123, custom-hybrid 123 of 123, custom-toolbox 123 of 123, native-mcp 123 of 123; model responses spent: baseline 476, custom-metricflow 416, custom-hybrid 458, custom-toolbox 250, native-mcp 632.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 63.4% | 75.6% | 82.9% | 46.3% | 82.9% |
| Confident-wrong | 12.2% | 2.4% | 0.0% | 4.9% | 2.4% |
| pass^1 | 63.4% | 75.6% | 82.9% | 46.3% | 82.9% |
| `conversation` (8) accuracy | 50.0% | 62.5% | 62.5% | 25.0% | 50.0% |
| `covered` (22) accuracy | 68.2% | 81.8% | 81.8% | 59.1% | 72.7% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% | 80.0% | 100.0% |
| `uncovered` (19) accuracy | 57.9% | 68.4% | 84.2% | 31.6% | 94.7% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.122 [-0.073, +0.317]: no difference.
- Confident-wrong: -0.098 [-0.220, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 42 (`baseline` 3 confident-wrong to right; `baseline` 2 right to unclear; `baseline` 2 wrong to right; `custom-hybrid` 4 confident-wrong to right; `custom-hybrid` 4 right to unclear; `custom-metricflow` 8 confident-wrong to right; `custom-metricflow` 3 confident-wrong to wrong; `custom-metricflow` 5 right to unclear; `custom-metricflow` 1 wrong to right; `custom-toolbox` 3 right to unclear; `native-mcp` 4 confident-wrong to right; `native-mcp` 3 right to unclear).

Turns judged: 3 (1 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 2 of 2 (1 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `baseline` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `baseline` `hard_revenue_per_session` run 3 turn 1: wrong / right
- `custom-hybrid` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `custom-hybrid` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `custom-hybrid` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `custom-hybrid` `hard_runner_up_channel_leads` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `custom-metricflow` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `native-mcp` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `native-mcp` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `native-mcp` `hard_mqls_social_september` run 3 turn 1: not judged yet

### `claude-sonnet-5-5`

Scored on partial: 2 run(s) of 41 of 41 cases; runs finished: custom-metricflow 123 of 123, custom-toolbox 123 of 123, native-mcp 83 of 123; model responses spent: custom-metricflow 421, custom-toolbox 247, native-mcp 386.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 52.4% | 45.1% | 82.9% |
| Confident-wrong | 1.2% | 4.9% | 0.0% |
| pass^2 | 51.2% | 43.9% | 80.5% |
| `conversation` (8) accuracy | 62.5% | 37.5% | 50.0% |
| `covered` (22) accuracy | 77.3% | 61.4% | 72.7% |
| `trap` (5) accuracy | 100.0% | 80.0% | 100.0% |
| `uncovered` (19) accuracy | 23.7% | 26.3% | 94.7% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 27 (`custom-metricflow` 1 confident-wrong to right; `custom-metricflow` 6 confident-wrong to wrong; `custom-metricflow` 5 right to unclear; `custom-metricflow` 3 wrong to right; `custom-toolbox` 6 right to unclear; `custom-toolbox` 1 wrong to declined; `native-mcp` 5 right to unclear).

Turns judged: 9 (2 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 8.
Confident-wrong turns the judge moved: 4 of 7 (3 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `hard_candidates_still_in_running` run 1 turn 1: wrong / confident-wrong
- `custom-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `custom-metricflow` `hard_top_channel_bookings` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_top_channel_bookings` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `custom-toolbox` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `native-mcp` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `native-mcp` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `native-mcp` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `native-mcp` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `native-mcp` `hard_top_channel_bookings` run 2 turn 1: not judged yet

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 41 of 41 cases; runs finished: baseline 41 of 123, custom-metricflow 123 of 123, custom-hybrid 41 of 123, custom-toolbox 41 of 123, native-mcp 41 of 123; model responses spent: baseline 195, custom-metricflow 480, custom-hybrid 180, custom-toolbox 78, native-mcp 290.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 48.8% | 73.2% | 82.9% | 39.0% | 90.2% |
| Confident-wrong | 19.5% | 4.9% | 0.0% | 14.6% | 0.0% |
| pass^1 | 48.8% | 73.2% | 82.9% | 39.0% | 90.2% |
| `conversation` (8) accuracy | 12.5% | 62.5% | 62.5% | 12.5% | 62.5% |
| `covered` (22) accuracy | 50.0% | 81.8% | 81.8% | 45.5% | 86.4% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% | 40.0% | 100.0% |
| `uncovered` (19) accuracy | 47.4% | 63.2% | 84.2% | 31.6% | 94.7% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.244 [+0.049, +0.439]: a difference.
- Confident-wrong: -0.146 [-0.293, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 12 (`custom-hybrid` 1 right to unclear; `custom-hybrid` 1 wrong to declined; `custom-metricflow` 4 confident-wrong to right; `custom-metricflow` 4 right to unclear; `custom-toolbox` 1 right to unclear; `native-mcp` 1 right to unclear).

Turns judged: 2 (1 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `custom-hybrid` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `custom-metricflow` `hard_customer_base_turkey` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `native-mcp` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet

### `claude-code-strict (haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 123 of 123, cc-metricflow 123 of 123, cc-native-mcp 123 of 123; model responses spent: cc-metricflow-compute 135, cc-metricflow 135, cc-native-mcp 135.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 79.7% | 68.3% | 83.7% |
| Confident-wrong | 0.0% | 2.4% | 0.8% |
| pass^3 | 73.2% | 61.0% | 78.0% |
| `conversation` (8) accuracy | 70.8% | 70.8% | 45.8% |
| `covered` (22) accuracy | 83.3% | 78.8% | 77.3% |
| `trap` (5) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (19) accuracy | 75.4% | 56.1% | 91.2% |

Turns judged: 4 (3 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 3.
Confident-wrong turns the judge moved: 1 of 1 (0 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `cc-metricflow` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `cc-metricflow-compute` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-metricflow-compute` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `cc-metricflow-compute` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `cc-metricflow-compute` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-metricflow-compute` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `cc-metricflow-compute` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `cc-native-mcp` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-native-mcp` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `cc-native-mcp` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `cc-native-mcp` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-native-mcp` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `cc-native-mcp` `hard_refund_rate_by_value` run 3 turn 1: confident-wrong / wrong

### `claude-code-strict (sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 123 of 123, cc-metricflow 123 of 123, cc-native-mcp 123 of 123; model responses spent: cc-metricflow-compute 135, cc-metricflow 135, cc-native-mcp 135.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 76.4% | 51.2% | 85.4% |
| Confident-wrong | 2.4% | 0.8% | 1.6% |
| pass^3 | 65.9% | 41.5% | 82.9% |
| `conversation` (8) accuracy | 58.3% | 45.8% | 58.3% |
| `covered` (22) accuracy | 77.3% | 69.7% | 80.3% |
| `trap` (5) accuracy | 93.3% | 93.3% | 100.0% |
| `uncovered` (19) accuracy | 75.4% | 29.8% | 91.2% |

Turns judged: 6 (5 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 6.
Confident-wrong turns the judge moved: 1 of 1 (1 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `cc-metricflow` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `cc-metricflow-compute` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-metricflow-compute` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `cc-native-mcp` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-native-mcp` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `cc-native-mcp` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `cc-native-mcp` `hard_mqls_social_september` run 3 turn 1: not judged yet

### `claude-code (haiku)`

Scored on partial: 1 run(s) of 41 of 41 cases; runs finished: cc-metricflow 41 of 123; model responses spent: cc-metricflow 45.

| | `cc-metricflow` |
|---|---|
| Accuracy | 41.5% |
| Confident-wrong | 7.3% |
| pass^1 | 41.5% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (22) accuracy | 77.3% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 7 (`cc-metricflow` 5 confident-wrong to wrong; `cc-metricflow` 2 unclear to declined).

Turns judged: 3 (3 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 3.

### `claude-code (sonnet)`

Scored on partial: 1 run(s) of 41 of 41 cases; runs finished: cc-metricflow 41 of 123; model responses spent: cc-metricflow 45.

| | `cc-metricflow` |
|---|---|
| Accuracy | 43.9% |
| Confident-wrong | 7.3% |
| pass^1 | 43.9% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (22) accuracy | 81.8% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 12 (`cc-metricflow` 10 confident-wrong to wrong; `cc-metricflow` 2 right to unclear).

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_top_channel_bookings` run 1 turn 1: not judged yet

### `claude-code (opus)`

Scored on partial: 1 run(s) of 41 of 41 cases; runs finished: cc-metricflow 41 of 123; model responses spent: cc-metricflow 45.

| | `cc-metricflow` |
|---|---|
| Accuracy | 51.2% |
| Confident-wrong | 0.0% |
| pass^1 | 51.2% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (22) accuracy | 90.9% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 5.3% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 11 (`cc-metricflow` 11 confident-wrong to wrong).

### `claude-code (fresh-haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 123 of 123; model responses spent: cc-metricflow 135.

| | `cc-metricflow` |
|---|---|
| Accuracy | 52.8% |
| Confident-wrong | 2.4% |
| pass^3 | 41.5% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (22) accuracy | 80.3% |
| `trap` (5) accuracy | 93.3% |
| `uncovered` (19) accuracy | 21.1% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 11 (`cc-metricflow` 4 confident-wrong to right; `cc-metricflow` 2 confident-wrong to wrong; `cc-metricflow` 4 right to unclear; `cc-metricflow` 1 wrong to right).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `cc-metricflow` `hard_mqls_social_september` run 3 turn 1: not judged yet

### `claude-code (fresh-sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 123 of 123; model responses spent: cc-metricflow 135.

| | `cc-metricflow` |
|---|---|
| Accuracy | 47.2% |
| Confident-wrong | 3.3% |
| pass^3 | 43.9% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (22) accuracy | 81.8% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 7.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 15 (`cc-metricflow` 12 confident-wrong to wrong; `cc-metricflow` 2 right to unclear; `cc-metricflow` 1 wrong to right).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet

### `claude-code (fresh-opus)`

Scored on partial: 1 run(s) of 41 of 41 cases; runs finished: cc-metricflow 41 of 123; model responses spent: cc-metricflow 45.

| | `cc-metricflow` |
|---|---|
| Accuracy | 48.8% |
| Confident-wrong | 0.0% |
| pass^1 | 48.8% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (22) accuracy | 81.8% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 10.5% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 6 (`cc-metricflow` 4 confident-wrong to wrong; `cc-metricflow` 1 right to unclear; `cc-metricflow` 1 wrong to right).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 41 of 41 cases; runs finished: native-bare 123 of 123, native-context-bare 123 of 123, native-context 123 of 123, native-governed 123 of 123, native-graph 123 of 123, native-kc-max 122 of 123, native-kc-reach 123 of 123, native-kc 123 of 123, native-shaped 123 of 123; model responses spent: native-bare 135, native-context-bare 135, native-context 136, native-governed 135, native-graph 135, native-kc-max 132, native-kc-reach 135, native-kc 135, native-shaped 135.

| | `native-bare` | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 61.0% | 90.2% | 90.2% | 70.7% | 53.7% | 85.4% | 82.9% | 65.9% | 63.4% |
| Confident-wrong | 34.1% | 0.0% | 0.0% | 0.0% | 19.5% | 2.4% | 9.8% | 14.6% | 14.6% |
| pass^1 | 61.0% | 90.2% | 90.2% | 70.7% | 53.7% | 85.4% | 82.9% | 65.9% | 63.4% |
| `conversation` (8) accuracy | 62.5% | 50.0% | 50.0% | 62.5% | 50.0% | 37.5% | 62.5% | 50.0% | 37.5% |
| `covered` (22) accuracy | 59.1% | 81.8% | 81.8% | 86.4% | 63.6% | 77.3% | 81.8% | 72.7% | 59.1% |
| `trap` (5) accuracy | 40.0% | 100.0% | 100.0% | 100.0% | 40.0% | 100.0% | 80.0% | 60.0% | 60.0% |
| `uncovered` (19) accuracy | 63.2% | 100.0% | 100.0% | 52.6% | 42.1% | 94.7% | 84.2% | 57.9% | 68.4% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 2 (`native-graph` 2 right to unclear).

Turns judged: 13 (6 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 13.
Confident-wrong turns the judge moved: 1 of 7 (1 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `native-graph` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `native-graph` `hard_mqls_social_september` run 1 turn 1: not judged yet

### `google-data-agent (LATEST_GA_MODEL)`

Scored on partial: 1 run(s) of 40 of 41 cases; runs finished: native-context-bare 122 of 123; model responses spent: native-context-bare 134.

| | `native-context-bare` |
|---|---|
| Accuracy | 92.5% |
| Confident-wrong | 2.5% |
| pass^1 | 92.5% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (21) accuracy | 90.5% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 94.7% |

Turns judged: 1 (0 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 1.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on partial: 2 run(s) of 41 of 41 cases; runs finished: native-context-bare 122 of 123; model responses spent: native-context-bare 134.

| | `native-context-bare` |
|---|---|
| Accuracy | 93.9% |
| Confident-wrong | 0.0% |
| pass^2 | 92.7% |
| `conversation` (8) accuracy | 68.8% |
| `covered` (22) accuracy | 88.6% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 100.0% |

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on all 3 runs of every case; runs finished: native-context-bare 123 of 123; model responses spent: native-context-bare 135.

| | `native-context-bare` |
|---|---|
| Accuracy | 94.3% |
| Confident-wrong | 0.0% |
| pass^3 | 92.7% |
| `conversation` (8) accuracy | 70.8% |
| `covered` (22) accuracy | 89.4% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 100.0% |

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, accuracy 94.3%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.187 [-0.309, -0.081], confident-wrong +0.016 [+0.000, +0.041]: not worth building (the check; 123 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.138 [-0.252, -0.041], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 123 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.496 [-0.650, -0.350], confident-wrong +0.073 [+0.008, +0.154]: not worth building (the check; 123 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.130 [-0.228, -0.049], confident-wrong +0.041 [+0.000, +0.106]: not worth building (the check; 123 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.398 [-0.545, -0.260], confident-wrong +0.008 [+0.000, +0.024]: not worth building (the check; 123 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.488 [-0.642, -0.333], confident-wrong +0.057 [+0.000, +0.130]: not worth building (the check; 123 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.114 [-0.207, -0.037], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 83 runs finished).
- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.220 [-0.341, -0.114], confident-wrong +0.041 [+0.008, +0.089]: not worth building (decides; 123 runs finished).
- `custom-hybrid` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.114 [-0.220, -0.024], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 41 runs finished).
- `custom-toolbox` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.553 [-0.707, -0.407], confident-wrong +0.146 [+0.049, +0.268]: not worth building (decides; 41 runs finished).
- `native-mcp` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.041 [-0.122, +0.016], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 41 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.146 [-0.260, -0.049], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 123 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.260 [-0.390, -0.138], confident-wrong +0.024 [+0.000, +0.065]: not worth building (the check; 123 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.106 [-0.203, -0.024], confident-wrong +0.008 [+0.000, +0.024]: not worth building (the check; 123 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.179 [-0.285, -0.089], confident-wrong +0.024 [+0.000, +0.065]: not worth building (the check; 123 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.431 [-0.569, -0.301], confident-wrong +0.008 [+0.000, +0.024]: not worth building (the check; 123 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.089 [-0.195, -0.000], confident-wrong +0.016 [+0.000, +0.049]: not worth building (the check; 123 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.528 [-0.683, -0.374], confident-wrong +0.073 [+0.000, +0.171]: not worth building (the check; 41 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.504 [-0.659, -0.350], confident-wrong +0.073 [+0.000, +0.171]: not worth building (the check; 41 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.431 [-0.585, -0.285], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 41 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.415 [-0.553, -0.285], confident-wrong +0.024 [+0.000, +0.065]: not worth building (the check; 123 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.472 [-0.618, -0.325], confident-wrong +0.033 [+0.000, +0.081]: not worth building (the check; 123 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 41 cases: accuracy -0.455 [-0.602, -0.309], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 41 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-hybrid`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow-compute`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-native-mcp`: the same verdict on every model, so the gap is not the model's.

## Every arm on the hard set v2

Written 2026-11-07T09:17Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-v2-local.jsonl`](eval-hard-v2-local.jsonl) and each live arm's `eval-hard-v2-<arm>.jsonl` under [the rule](RULE.md): 55 cases of `services/semantic-agent/evals/semantic_bet_hard_v2.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
162 of `baseline`'s 162 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `claude-haiku-5-5`

Scored on partial: 1 run(s) of 41 of 55 cases; runs finished: baseline 121 of 165, custom-metricflow 123 of 165, custom-hybrid 123 of 165, custom-toolbox 123 of 165, native-mcp 123 of 165; model responses spent: baseline 476, custom-metricflow 416, custom-hybrid 458, custom-toolbox 250, native-mcp 632.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 63.4% | 75.6% | 82.9% | 46.3% | 82.9% |
| Confident-wrong | 12.2% | 2.4% | 0.0% | 4.9% | 2.4% |
| pass^1 | 63.4% | 75.6% | 82.9% | 46.3% | 82.9% |
| `composable` (14) accuracy | 71.4% | 78.6% | 100.0% | 42.9% | 92.9% |
| `conversation` (8) accuracy | 50.0% | 62.5% | 62.5% | 25.0% | 50.0% |
| `covered` (22) accuracy | 68.2% | 81.8% | 81.8% | 59.1% | 72.7% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% | 80.0% | 100.0% |
| `uncovered` (5) accuracy | 20.0% | 40.0% | 40.0% | 0.0% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.122 [-0.073, +0.317]: no difference.
- Confident-wrong: -0.098 [-0.220, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 42 (`baseline` 3 confident-wrong to right; `baseline` 2 right to unclear; `baseline` 2 wrong to right; `custom-hybrid` 4 confident-wrong to right; `custom-hybrid` 4 right to unclear; `custom-metricflow` 8 confident-wrong to right; `custom-metricflow` 3 confident-wrong to wrong; `custom-metricflow` 5 right to unclear; `custom-metricflow` 1 wrong to right; `custom-toolbox` 3 right to unclear; `native-mcp` 4 confident-wrong to right; `native-mcp` 3 right to unclear).

Turns judged: 3 (1 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 2 of 2 (1 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `baseline` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `baseline` `hard_revenue_per_session` run 3 turn 1: wrong / right
- `custom-hybrid` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `custom-hybrid` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `custom-hybrid` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `custom-hybrid` `hard_runner_up_channel_leads` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `custom-metricflow` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `native-mcp` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `native-mcp` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `native-mcp` `hard_mqls_social_september` run 3 turn 1: not judged yet

### `claude-sonnet-5-5`

Scored on partial: 1 run(s) of 41 of 55 cases; runs finished: custom-metricflow 123 of 165, custom-toolbox 123 of 165, native-mcp 83 of 165; model responses spent: custom-metricflow 421, custom-toolbox 247, native-mcp 386.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 51.2% | 46.3% | 85.4% |
| Confident-wrong | 2.4% | 4.9% | 0.0% |
| pass^1 | 51.2% | 46.3% | 85.4% |
| `composable` (14) accuracy | 21.4% | 35.7% | 92.9% |
| `conversation` (8) accuracy | 62.5% | 37.5% | 50.0% |
| `covered` (22) accuracy | 77.3% | 63.6% | 77.3% |
| `trap` (5) accuracy | 100.0% | 80.0% | 100.0% |
| `uncovered` (5) accuracy | 20.0% | 0.0% | 100.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 27 (`custom-metricflow` 1 confident-wrong to right; `custom-metricflow` 6 confident-wrong to wrong; `custom-metricflow` 5 right to unclear; `custom-metricflow` 3 wrong to right; `custom-toolbox` 6 right to unclear; `custom-toolbox` 1 wrong to declined; `native-mcp` 5 right to unclear).

Turns judged: 9 (2 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 8.
Confident-wrong turns the judge moved: 4 of 7 (3 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `hard_candidates_still_in_running` run 1 turn 1: wrong / confident-wrong
- `custom-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `custom-metricflow` `hard_top_channel_bookings` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_top_channel_bookings` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `custom-toolbox` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `native-mcp` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `native-mcp` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `native-mcp` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `native-mcp` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `native-mcp` `hard_top_channel_bookings` run 2 turn 1: not judged yet

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 41 of 55 cases; runs finished: baseline 41 of 165, custom-metricflow 123 of 165, custom-hybrid 41 of 165, custom-toolbox 41 of 165, native-mcp 41 of 165; model responses spent: baseline 195, custom-metricflow 480, custom-hybrid 180, custom-toolbox 78, native-mcp 290.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 48.8% | 73.2% | 82.9% | 39.0% | 90.2% |
| Confident-wrong | 19.5% | 4.9% | 0.0% | 14.6% | 0.0% |
| pass^1 | 48.8% | 73.2% | 82.9% | 39.0% | 90.2% |
| `composable` (14) accuracy | 64.3% | 71.4% | 100.0% | 42.9% | 92.9% |
| `conversation` (8) accuracy | 12.5% | 62.5% | 62.5% | 12.5% | 62.5% |
| `covered` (22) accuracy | 50.0% | 81.8% | 81.8% | 45.5% | 86.4% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% | 40.0% | 100.0% |
| `uncovered` (5) accuracy | 0.0% | 40.0% | 40.0% | 0.0% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.244 [+0.049, +0.439]: a difference.
- Confident-wrong: -0.146 [-0.293, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 12 (`custom-hybrid` 1 right to unclear; `custom-hybrid` 1 wrong to declined; `custom-metricflow` 4 confident-wrong to right; `custom-metricflow` 4 right to unclear; `custom-toolbox` 1 right to unclear; `native-mcp` 1 right to unclear).

Turns judged: 2 (1 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `custom-hybrid` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `custom-metricflow` `hard_customer_base_turkey` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `native-mcp` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet

### `claude-code-strict (haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 165 of 165, cc-metricflow 165 of 165, cc-native-mcp 165 of 165; model responses spent: cc-metricflow-compute 177, cc-metricflow 177, cc-native-mcp 177.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 74.5% | 64.2% | 87.9% |
| Confident-wrong | 3.0% | 3.6% | 1.2% |
| pass^3 | 69.1% | 58.2% | 83.6% |
| `composable` (21) accuracy | 88.9% | 66.7% | 96.8% |
| `conversation` (8) accuracy | 75.0% | 70.8% | 58.3% |
| `covered` (23) accuracy | 85.5% | 81.2% | 78.3% |
| `trap` (5) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (11) accuracy | 24.2% | 24.2% | 90.9% |

Turns judged: 2 (2 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 2.

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `cc-metricflow` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `cc-metricflow-compute` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-metricflow-compute` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `cc-metricflow-compute` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `cc-metricflow-compute` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `cc-native-mcp` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-native-mcp` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `cc-native-mcp` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-native-mcp` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `cc-native-mcp` `hard_mqls_social_september` run 3 turn 1: not judged yet
- `cc-native-mcp` `hard_runner_up_channel_leads` run 1 turn 1: not judged yet
- `cc-native-mcp` `hv2_median_gap_between_orders` run 2 turn 1: not judged yet
- `cc-native-mcp` `hv2_median_gap_between_orders` run 3 turn 1: not judged yet

### `claude-code-strict (sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow-compute 165 of 165, cc-metricflow 165 of 165, cc-native-mcp 165 of 165; model responses spent: cc-metricflow-compute 177, cc-metricflow 177, cc-native-mcp 177.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 71.5% | 51.5% | 86.1% |
| Confident-wrong | 6.7% | 6.7% | 1.2% |
| pass^3 | 61.8% | 43.6% | 83.6% |
| `composable` (21) accuracy | 81.0% | 44.4% | 92.1% |
| `conversation` (8) accuracy | 62.5% | 50.0% | 50.0% |
| `covered` (23) accuracy | 81.2% | 69.6% | 78.3% |
| `trap` (5) accuracy | 93.3% | 93.3% | 100.0% |
| `uncovered` (11) accuracy | 33.3% | 27.3% | 90.9% |

Turns judged: 9 (4 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 8.
Confident-wrong turns the judge moved: 3 of 5 (2 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `cc-metricflow` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `cc-metricflow` `hv2_signups_never_ordered` run 1 turn 1: not judged yet
- `cc-metricflow-compute` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-metricflow-compute` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `cc-metricflow-compute` `hv2_spend_on_days_without_email_booking` run 3 turn 1: confident-wrong / wrong
- `cc-native-mcp` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-native-mcp` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet
- `cc-native-mcp` `hard_cost_per_booking_rise` run 3 turn 1: not judged yet
- `cc-native-mcp` `hv2_median_gap_between_orders` run 1 turn 1: not judged yet
- `cc-native-mcp` `hv2_median_gap_between_orders` run 2 turn 1: not judged yet
- `cc-native-mcp` `hv2_median_gap_between_orders` run 3 turn 1: not judged yet

### `claude-code-strict (opus)`

Scored on partial: 1 run(s) of 50 of 55 cases; runs finished: cc-metricflow-compute 50 of 165, cc-metricflow 50 of 165, cc-native-mcp 50 of 165; model responses spent: cc-metricflow-compute 54, cc-metricflow 54, cc-native-mcp 54.

| | `cc-metricflow-compute` | `cc-metricflow` | `cc-native-mcp` |
|---|---|---|---|
| Accuracy | 74.0% | 42.0% | 82.0% |
| Confident-wrong | 0.0% | 4.0% | 0.0% |
| pass^1 | 74.0% | 42.0% | 82.0% |
| `composable` (19) accuracy | 78.9% | 5.3% | 84.2% |
| `conversation` (8) accuracy | 87.5% | 75.0% | 75.0% |
| `covered` (23) accuracy | 87.0% | 78.3% | 82.6% |
| `trap` (5) accuracy | 100.0% | 100.0% | 100.0% |
| `uncovered` (8) accuracy | 25.0% | 25.0% | 75.0% |

Turns judged: 1 (0 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 1.
Confident-wrong turns the judge moved: 1 of 1 (1 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_top_channel_bookings` run 1 turn 1: not judged yet
- `cc-metricflow-compute` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-metricflow-compute` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-metricflow-compute` `hv2_signups_never_ordered` run 1 turn 1: not judged yet
- `cc-native-mcp` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-native-mcp` `hv2_median_gap_between_orders` run 1 turn 1: not judged yet

### `claude-code (haiku)`

Scored on partial: 1 run(s) of 55 of 55 cases; runs finished: cc-metricflow 55 of 165; model responses spent: cc-metricflow 59.

| | `cc-metricflow` |
|---|---|
| Accuracy | 32.7% |
| Confident-wrong | 12.7% |
| pass^1 | 32.7% |
| `composable` (21) accuracy | 0.0% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (23) accuracy | 78.3% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 7 (`cc-metricflow` 5 confident-wrong to wrong; `cc-metricflow` 2 unclear to declined).

Turns judged: 3 (3 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 3.

### `claude-code (sonnet)`

Scored on partial: 1 run(s) of 55 of 55 cases; runs finished: cc-metricflow 55 of 165; model responses spent: cc-metricflow 59.

| | `cc-metricflow` |
|---|---|
| Accuracy | 34.5% |
| Confident-wrong | 12.7% |
| pass^1 | 34.5% |
| `composable` (21) accuracy | 0.0% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (23) accuracy | 82.6% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 12 (`cc-metricflow` 10 confident-wrong to wrong; `cc-metricflow` 2 right to unclear).

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_top_channel_bookings` run 1 turn 1: not judged yet

### `claude-code (opus)`

Scored on partial: 1 run(s) of 55 of 55 cases; runs finished: cc-metricflow 55 of 165; model responses spent: cc-metricflow 59.

| | `cc-metricflow` |
|---|---|
| Accuracy | 43.6% |
| Confident-wrong | 3.6% |
| pass^1 | 43.6% |
| `composable` (21) accuracy | 4.8% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (23) accuracy | 91.3% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 18.2% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 11 (`cc-metricflow` 11 confident-wrong to wrong).

### `claude-code (fresh-haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 165 of 165; model responses spent: cc-metricflow 177.

| | `cc-metricflow` |
|---|---|
| Accuracy | 45.5% |
| Confident-wrong | 7.3% |
| pass^3 | 34.5% |
| `composable` (21) accuracy | 27.0% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (23) accuracy | 81.2% |
| `trap` (5) accuracy | 93.3% |
| `uncovered` (11) accuracy | 6.1% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 11 (`cc-metricflow` 4 confident-wrong to right; `cc-metricflow` 2 confident-wrong to wrong; `cc-metricflow` 4 right to unclear; `cc-metricflow` 1 wrong to right).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_mqls_social_september` run 2 turn 1: not judged yet
- `cc-metricflow` `hard_mqls_social_september` run 3 turn 1: not judged yet

### `claude-code (fresh-sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 165 of 165; model responses spent: cc-metricflow 177.

| | `cc-metricflow` |
|---|---|
| Accuracy | 37.0% |
| Confident-wrong | 6.7% |
| pass^3 | 34.5% |
| `composable` (21) accuracy | 6.3% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (23) accuracy | 82.6% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 0.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 15 (`cc-metricflow` 12 confident-wrong to wrong; `cc-metricflow` 2 right to unclear; `cc-metricflow` 1 wrong to right).

Turns judged: 3 (0 the code left unclear, 3 confident-wrong with a hedge outside the list); verdicts that stood: 3.
Confident-wrong turns the judge moved: 3 of 3 (3 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_cost_per_booking_rise` run 2 turn 1: not judged yet

### `claude-code (fresh-opus)`

Scored on partial: 1 run(s) of 55 of 55 cases; runs finished: cc-metricflow 55 of 165; model responses spent: cc-metricflow 59.

| | `cc-metricflow` |
|---|---|
| Accuracy | 38.2% |
| Confident-wrong | 3.6% |
| pass^1 | 38.2% |
| `composable` (21) accuracy | 4.8% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (23) accuracy | 82.6% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 9.1% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 6 (`cc-metricflow` 4 confident-wrong to wrong; `cc-metricflow` 1 right to unclear; `cc-metricflow` 1 wrong to right).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 41 of 55 cases; runs finished: native-bare 165 of 165, native-context-bare 123 of 165, native-context 165 of 165, native-governed 123 of 165, native-graph 123 of 165, native-kc-max 165 of 165, native-kc-reach 123 of 165, native-kc 123 of 165, native-shaped 123 of 165; model responses spent: native-bare 177, native-context-bare 135, native-context 178, native-governed 135, native-graph 135, native-kc-max 177, native-kc-reach 135, native-kc 135, native-shaped 135.

| | `native-bare` | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 61.0% | 90.2% | 90.2% | 70.7% | 53.7% | 85.4% | 82.9% | 65.9% | 63.4% |
| Confident-wrong | 34.1% | 0.0% | 0.0% | 0.0% | 19.5% | 2.4% | 9.8% | 14.6% | 14.6% |
| pass^1 | 61.0% | 90.2% | 90.2% | 70.7% | 53.7% | 85.4% | 82.9% | 65.9% | 63.4% |
| `composable` (14) accuracy | 64.3% | 100.0% | 100.0% | 71.4% | 35.7% | 92.9% | 85.7% | 50.0% | 64.3% |
| `conversation` (8) accuracy | 62.5% | 50.0% | 50.0% | 62.5% | 50.0% | 37.5% | 62.5% | 50.0% | 37.5% |
| `covered` (22) accuracy | 59.1% | 81.8% | 81.8% | 86.4% | 63.6% | 77.3% | 81.8% | 72.7% | 59.1% |
| `trap` (5) accuracy | 40.0% | 100.0% | 100.0% | 100.0% | 40.0% | 100.0% | 80.0% | 60.0% | 60.0% |
| `uncovered` (5) accuracy | 60.0% | 100.0% | 100.0% | 0.0% | 60.0% | 100.0% | 80.0% | 80.0% | 80.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 8 (`native-bare` 3 right to unclear; `native-context` 2 right to unclear; `native-graph` 2 right to unclear; `native-kc-max` 1 right to unclear).

Turns judged: 13 (6 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 13.
Confident-wrong turns the judge moved: 1 of 7 (1 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `native-bare` `hv2_median_gap_between_orders` run 1 turn 1: not judged yet
- `native-bare` `hv2_median_gap_between_orders` run 2 turn 1: not judged yet
- `native-bare` `hv2_median_gap_between_orders` run 3 turn 1: not judged yet
- `native-context` `hv2_median_gap_between_orders` run 1 turn 1: not judged yet
- `native-context` `hv2_median_gap_between_orders` run 3 turn 1: not judged yet
- `native-graph` `hard_cost_per_booking_rise` run 1 turn 1: not judged yet
- `native-graph` `hard_mqls_social_september` run 1 turn 1: not judged yet
- `native-kc-max` `hv2_median_gap_between_orders` run 2 turn 1: not judged yet

### `google-data-agent (LATEST_GA_MODEL)`

Scored on partial: 1 run(s) of 40 of 55 cases; runs finished: native-context-bare 122 of 165; model responses spent: native-context-bare 134.

| | `native-context-bare` |
|---|---|
| Accuracy | 92.5% |
| Confident-wrong | 2.5% |
| pass^1 | 92.5% |
| `composable` (14) accuracy | 92.9% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (21) accuracy | 90.5% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (5) accuracy | 100.0% |

Turns judged: 1 (0 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 1.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on all 3 runs of every case; runs finished: native-context-bare 165 of 165; model responses spent: native-context-bare 177.

| | `native-context-bare` |
|---|---|
| Accuracy | 93.9% |
| Confident-wrong | 0.0% |
| pass^3 | 92.7% |
| `composable` (21) accuracy | 100.0% |
| `conversation` (8) accuracy | 70.8% |
| `covered` (23) accuracy | 89.9% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (11) accuracy | 90.9% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 3 (`native-context-bare` 3 right to unclear).

Turns still unclear after judging (counted as wrong):

- `native-context-bare` `hv2_median_gap_between_orders` run 1 turn 1: not judged yet
- `native-context-bare` `hv2_median_gap_between_orders` run 2 turn 1: not judged yet
- `native-context-bare` `hv2_median_gap_between_orders` run 3 turn 1: not judged yet

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on partial: 1 run(s) of 41 of 55 cases; runs finished: native-context-bare 123 of 165; model responses spent: native-context-bare 135.

| | `native-context-bare` |
|---|---|
| Accuracy | 95.1% |
| Confident-wrong | 0.0% |
| pass^1 | 95.1% |
| `composable` (14) accuracy | 100.0% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (22) accuracy | 90.9% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (5) accuracy | 100.0% |

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, accuracy 93.9%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 55 cases: accuracy -0.187 [-0.309, -0.081], confident-wrong +0.016 [+0.000, +0.041]: not worth building (the check; 123 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 55 cases: accuracy -0.138 [-0.252, -0.041], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 123 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 55 cases: accuracy -0.496 [-0.650, -0.350], confident-wrong +0.073 [+0.008, +0.154]: not worth building (the check; 123 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 55 cases: accuracy -0.130 [-0.228, -0.049], confident-wrong +0.041 [+0.000, +0.106]: not worth building (the check; 123 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 55 cases: accuracy -0.398 [-0.545, -0.260], confident-wrong +0.008 [+0.000, +0.024]: not worth building (the check; 123 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 55 cases: accuracy -0.488 [-0.642, -0.333], confident-wrong +0.057 [+0.000, +0.130]: not worth building (the check; 123 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 55 cases: accuracy -0.114 [-0.207, -0.037], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 83 runs finished).
- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 55 cases: accuracy -0.220 [-0.341, -0.114], confident-wrong +0.041 [+0.008, +0.089]: not worth building (decides; 123 runs finished).
- `custom-hybrid` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 55 cases: accuracy -0.114 [-0.220, -0.024], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 41 runs finished).
- `custom-toolbox` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 55 cases: accuracy -0.553 [-0.707, -0.407], confident-wrong +0.146 [+0.049, +0.268]: not worth building (decides; 41 runs finished).
- `native-mcp` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 55 cases: accuracy -0.041 [-0.122, +0.016], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 41 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.194 [-0.297, -0.103], confident-wrong +0.030 [+0.006, +0.067]: not worth building (the check; 165 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.297 [-0.418, -0.182], confident-wrong +0.036 [+0.006, +0.073]: not worth building (the check; 165 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.061 [-0.139, +0.012], confident-wrong +0.012 [+0.000, +0.030]: not worth building (the check; 165 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.224 [-0.327, -0.133], confident-wrong +0.067 [+0.024, +0.115]: not worth building (the check; 165 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.424 [-0.545, -0.303], confident-wrong +0.067 [+0.018, +0.121]: not worth building (the check; 165 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.079 [-0.152, -0.024], confident-wrong +0.012 [+0.000, +0.030]: not worth building (the check; 165 runs finished).
- `cc-metricflow-compute` (rung 4) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 50 of 55 cases: accuracy -0.193 [-0.320, -0.073], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 50 runs finished).
- `cc-metricflow` (rung 4) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 50 of 55 cases: accuracy -0.513 [-0.653, -0.373], confident-wrong +0.040 [+0.000, +0.100]: not worth building (the check; 50 runs finished).
- `cc-native-mcp` (rung 3) on `claude-code-strict (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 50 of 55 cases: accuracy -0.113 [-0.213, -0.033], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 50 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.612 [-0.739, -0.485], confident-wrong +0.127 [+0.055, +0.218]: not worth building (the check; 55 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.594 [-0.727, -0.461], confident-wrong +0.127 [+0.055, +0.218]: not worth building (the check; 55 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.503 [-0.636, -0.364], confident-wrong +0.036 [+0.000, +0.091]: not worth building (the check; 55 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.485 [-0.606, -0.364], confident-wrong +0.073 [+0.018, +0.139]: not worth building (the check; 165 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.570 [-0.697, -0.442], confident-wrong +0.067 [+0.018, +0.127]: not worth building (the check; 165 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 55 of 55 cases: accuracy -0.558 [-0.691, -0.424], confident-wrong +0.036 [+0.000, +0.091]: not worth building (the check; 55 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-hybrid`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow-compute`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-native-mcp`: the same verdict on every model, so the gap is not the model's.

### The rule on both sets

RULE.md § Changes since freezing (#356): each set goes through the rule on its own; an arm of ours is worth building only if step 2 holds on both sets, and where they disagree the cheaper rung wins, as a tie does.
- The managed best on the frozen set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 92.1%.
- The managed best on the hard set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 94.3%.
- `custom-metricflow` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-hybrid` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-lightdash` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
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
- `cc-native-mcp` on `claude-code-strict (haiku)` (the check): the frozen set: worth; the hard set: not worth; on both sets: not worth building (the sets disagree: the cheaper rung wins).
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
- Step 3 (RULE.md § The rule, 3; it applies when no arm of ours is worth building): the arms with no accuracy difference from the managed best on both sets: `native-mcp` on `nvidia/nemotron-3.5-super-vl:free` (rung 3), `cc-native-mcp` on `claude-code-strict (sonnet)` (rung 3), `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)` (rung 1), `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)` (rung 1), `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)` (rung 1), `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)` (rung 1).
  The cheapest rung among them is 1: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)`, `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, FAST)`; within a rung the arm with fewer moving parts named in its finding wins (§ The cost ladder), which the report names.
