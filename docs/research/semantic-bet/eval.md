# Every arm on the bet's sets

Each set is scored on its own under [the rule](RULE.md), with its own comparison against the managed best: [the frozen set](#every-arm-on-the-frozen-set), then [the hard set](#every-arm-on-the-hard-set) (#356, #364).

## Every arm on the frozen set

Written 2026-11-05T00:28Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 1 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
0 of `baseline`'s 336 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 41 of 96 cases; runs finished: baseline 48 of 96, custom-metricflow 110 of 96, custom-hybrid 96 of 96, custom-lightdash 41 of 96; model responses spent: baseline 221, custom-metricflow 409, custom-hybrid 409, custom-lightdash 77.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-lightdash` |
|---|---|---|---|---|
| Accuracy | 63.4% | 95.1% | 97.6% | 58.5% |
| Confident-wrong | 14.6% | 0.0% | 0.0% | 9.8% |
| pass^1 | 63.4% | 95.1% | 97.6% | 58.5% |
| `covered` (39) accuracy | 64.1% | 100.0% | 100.0% | 61.5% |
| `distractor` (2) accuracy | 100.0% | 100.0% | 100.0% | 50.0% |
| `trap` (8) accuracy | 50.0% | 100.0% | 100.0% | 50.0% |
| `uncovered` (2) accuracy | 50.0% | 0.0% | 50.0% | 0.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.317 [+0.171, +0.463]: a difference.
- Confident-wrong: -0.146 [-0.268, -0.049]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 9 (4 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 9.
Confident-wrong turns the judge moved: 3 of 5 (3 to wrong, hedged; 0 to unclear).

### `claude-haiku-5-5`

Scored on all 1 runs of every case; runs finished: baseline 288 of 96, custom-metricflow 288 of 96, custom-hybrid 288 of 96, custom-toolbox 288 of 96, native-mcp 288 of 96; model responses spent: baseline 1038, custom-metricflow 962, custom-hybrid 1052, custom-toolbox 485, native-mcp 1383.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 62.5% | 79.2% | 77.1% | 42.7% | 91.7% |
| Confident-wrong | 7.3% | 3.1% | 3.1% | 2.1% | 3.1% |
| pass^1 | 62.5% | 79.2% | 77.1% | 42.7% | 91.7% |
| `conversation` (7) accuracy | 57.1% | 85.7% | 100.0% | 42.9% | 57.1% |
| `covered` (67) accuracy | 73.1% | 95.5% | 88.1% | 52.2% | 91.0% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% | 75.0% | 100.0% |
| `trap` (11) accuracy | 72.7% | 90.9% | 100.0% | 54.5% | 100.0% |
| `uncovered` (29) accuracy | 37.9% | 41.4% | 51.7% | 20.7% | 93.1% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.167 [+0.062, +0.271]: a difference.
- Confident-wrong: -0.042 [-0.104, +0.021]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 23 (11 the code left unclear, 12 confident-wrong with a hedge outside the list); verdicts that stood: 21.
Confident-wrong turns the judge moved: 11 of 12 (9 to wrong, hedged; 2 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `damaged_returns` run 3 turn 1: wrong / declined
- `baseline` `shipped_orders` run 3 turn 1: declined / wrong
- `custom-hybrid` `active_customers` run 1 turn 1: not judged yet
- `custom-hybrid` `bet_customers_over_three_orders` run 1 turn 1: not judged yet
- `custom-hybrid` `bet_customers_over_three_orders` run 2 turn 1: not judged yet
- `custom-hybrid` `cancelled_total` run 1 turn 1: not judged yet
- `custom-hybrid` `cancelled_total` run 2 turn 1: not judged yet
- `custom-hybrid` `candidates_in_interview_as_of` run 1 turn 1: not judged yet
- `custom-hybrid` `candidates_in_interview_as_of` run 2 turn 1: not judged yet
- `custom-hybrid` `candidates_in_interview_as_of` run 3 turn 1: not judged yet
- `custom-hybrid` `engaged_customers_week` run 1 turn 1: not judged yet
- `custom-hybrid` `engaged_customers_week` run 2 turn 1: not judged yet
- `custom-hybrid` `engaged_customers_week` run 3 turn 1: not judged yet
- `custom-hybrid` `orders_over_100` run 2 turn 1: not judged yet
- `custom-hybrid` `partners_engaged_one_day` run 1 turn 1: not judged yet
- `custom-hybrid` `partners_engaged_one_day` run 2 turn 1: not judged yet
- `custom-hybrid` `partners_engaged_one_day` run 3 turn 1: not judged yet
- `native-mcp` `active_customers` run 2 turn 1: not judged yet
- `native-mcp` `candidates_in_interview_as_of` run 1 turn 1: not judged yet
- `native-mcp` `partners_engaged_one_day` run 2 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-hybrid` `calls_about_returns` run 3 turn 1: not judged yet
- `custom-hybrid` `signups_september` run 2 turn 1: not judged yet
- `custom-hybrid` `signups_september` run 3 turn 1: not judged yet
- `native-mcp` `bet_applicants_reaching_interview` run 2 turn 1: not judged yet
- `native-mcp` `signups_september` run 3 turn 1: not judged yet

### `claude-sonnet-5-5`

Scored on all 1 runs of every case; runs finished: custom-metricflow 288 of 96, custom-toolbox 288 of 96, native-mcp 288 of 96; model responses spent: custom-metricflow 931, custom-toolbox 472, native-mcp 1290.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 76.0% | 41.7% | 95.8% |
| Confident-wrong | 1.0% | 3.1% | 0.0% |
| pass^1 | 76.0% | 41.7% | 95.8% |
| `conversation` (7) accuracy | 100.0% | 42.9% | 71.4% |
| `covered` (67) accuracy | 98.5% | 50.7% | 95.5% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 50.0% | 75.0% |
| `trap` (11) accuracy | 100.0% | 54.5% | 100.0% |
| `uncovered` (29) accuracy | 24.1% | 20.7% | 96.6% |

Turns judged: 8 (8 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 8.

Turns still unclear after judging (counted as wrong):

- `custom-toolbox` `bet_top_campaign_spend` run 2 turn 1: not judged yet
- `custom-toolbox` `signup_to_first_order_rate` run 1 turn 1: not judged yet
- `custom-toolbox` `signup_to_first_order_rate` run 3 turn 1: not judged yet
- `native-mcp` `calls_about_returns` run 3 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-toolbox` `return_rate_september` run 1 turn 1: not judged yet
- `custom-toolbox` `return_rate_september` run 2 turn 1: not judged yet
- `custom-toolbox` `revenue_fiscal_q3` run 1 turn 1: not judged yet
- `custom-toolbox` `revenue_fiscal_q3` run 3 turn 1: not judged yet

### `claude-opus-5-5`

Scored on all 1 runs of every case; runs finished: custom-metricflow 288 of 96; model responses spent: custom-metricflow 932.

| | `custom-metricflow` |
|---|---|
| Accuracy | 76.0% |
| Confident-wrong | 2.1% |
| pass^1 | 76.0% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 100.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 20.7% |

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `bet_istanbul_warmer` run 1 turn 1: not judged yet
- `custom-metricflow` `bet_istanbul_warmer` run 2 turn 1: not judged yet
- `custom-metricflow` `bet_istanbul_warmer` run 3 turn 1: not judged yet
- `custom-metricflow` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `custom-metricflow` `cancelled_total` run 2 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-metricflow` `bet_peak_checkout_hour` run 2 turn 1: not judged yet

### `claude-code (haiku)`

Scored on all 1 runs of every case; runs finished: cc-metricflow 96 of 96; model responses spent: cc-metricflow 102.

| | `cc-metricflow` |
|---|---|
| Accuracy | 66.7% |
| Confident-wrong | 5.2% |
| pass^1 | 66.7% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 92.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 75.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 6.9% |

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `bet_ad_spend_per_order` run 1 turn 1: not judged yet
- `cc-metricflow` `bet_istanbul_warmer` run 1 turn 1: not judged yet
- `cc-metricflow` `bet_median_days_to_hire` run 1 turn 1: not judged yet
- `cc-metricflow` `bet_median_reply_hours` run 1 turn 1: not judged yet
- `cc-metricflow` `bet_p90_order` run 1 turn 1: not judged yet
- `cc-metricflow` `bet_weekday_avg_spend` run 1 turn 1: not judged yet

### `claude-code (sonnet)`

Scored on all 1 runs of every case; runs finished: cc-metricflow 96 of 96; model responses spent: cc-metricflow 102.

| | `cc-metricflow` |
|---|---|
| Accuracy | 70.8% |
| Confident-wrong | 1.0% |
| pass^1 | 70.8% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 100.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 3.4% |

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `median_order_value` run 1 turn 1: not judged yet

### `claude-code (opus)`

Scored on all 1 runs of every case; runs finished: cc-metricflow 96 of 96; model responses spent: cc-metricflow 102.

| | `cc-metricflow` |
|---|---|
| Accuracy | 70.8% |
| Confident-wrong | 4.2% |
| pass^1 | 70.8% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 98.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 6.9% |

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `bet_ad_spend_per_order` run 1 turn 1: not judged yet
- `cc-metricflow` `bet_median_days_to_hire` run 1 turn 1: not judged yet
- `cc-metricflow` `bet_p90_order` run 1 turn 1: not judged yet
- `cc-metricflow` `bet_peak_checkout_hour` run 1 turn 1: not judged yet

### `claude-code (fresh-haiku)`

Scored on all 1 runs of every case; runs finished: cc-metricflow 96 of 96; model responses spent: cc-metricflow 102.

| | `cc-metricflow` |
|---|---|
| Accuracy | 72.9% |
| Confident-wrong | 3.1% |
| pass^1 | 72.9% |
| `conversation` (7) accuracy | 85.7% |
| `covered` (67) accuracy | 97.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 17.2% |

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `bet_peak_checkout_hour` run 1 turn 1: not judged yet

### `claude-code (fresh-sonnet)`

Scored on all 1 runs of every case; runs finished: cc-metricflow 96 of 96; model responses spent: cc-metricflow 102.

| | `cc-metricflow` |
|---|---|
| Accuracy | 74.0% |
| Confident-wrong | 3.1% |
| pass^1 | 74.0% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 98.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 75.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 17.2% |

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `bet_peak_checkout_hour` run 1 turn 1: not judged yet

### `claude-code (fresh-opus)`

Scored on partial: 1 run(s) of 20 of 96 cases; runs finished: cc-metricflow 20 of 96; model responses spent: cc-metricflow 21.

| | `cc-metricflow` |
|---|---|
| Accuracy | 70.0% |
| Confident-wrong | 0.0% |
| pass^1 | 70.0% |
| `conversation` (1) accuracy | 100.0% |
| `covered` (14) accuracy | 100.0% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (1) accuracy | 100.0% |
| `trap` (3) accuracy | 100.0% |
| `uncovered` (6) accuracy | 0.0% |

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 95 of 96 cases; runs finished: native-bare 287 of 96, native-context-bare 288 of 96, native-context 288 of 96, native-governed 288 of 96, native-graph 288 of 96, native-kc-max 288 of 96, native-kc-reach 288 of 96, native-kc 288 of 96, native-shaped 288 of 96; model responses spent: native-bare 305, native-context-bare 306, native-context 306, native-governed 306, native-graph 306, native-kc-max 306, native-kc-reach 306, native-kc 306, native-shaped 306.

| | `native-bare` | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 80.0% | 89.5% | 87.4% | 72.6% | 61.1% | 90.5% | 86.3% | 64.2% | 61.1% |
| Confident-wrong | 15.8% | 4.2% | 6.3% | 1.1% | 7.4% | 5.3% | 7.4% | 4.2% | 5.3% |
| pass^1 | 80.0% | 89.5% | 87.4% | 72.6% | 61.1% | 90.5% | 86.3% | 64.2% | 61.1% |
| `conversation` (7) accuracy | 28.6% | 71.4% | 71.4% | 71.4% | 42.9% | 42.9% | 28.6% | 57.1% | 28.6% |
| `covered` (66) accuracy | 75.8% | 97.0% | 95.5% | 90.9% | 66.7% | 89.4% | 86.4% | 71.2% | 65.2% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 66.7% |
| `planted` (4) accuracy | 75.0% | 100.0% | 100.0% | 75.0% | 75.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `trap` (10) accuracy | 60.0% | 100.0% | 100.0% | 100.0% | 60.0% | 90.0% | 90.0% | 60.0% | 40.0% |
| `uncovered` (29) accuracy | 89.7% | 72.4% | 69.0% | 31.0% | 48.3% | 93.1% | 86.2% | 48.3% | 51.7% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 6 (`native-governed` 1 confident-wrong to wrong; `native-governed` 2 unclear to declined; `native-shaped` 1 confident-wrong to wrong; `native-shaped` 2 unclear to declined).

Turns judged: 24 (19 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 24.
Confident-wrong turns the judge moved: 1 of 5 (1 to wrong, hedged; 0 to unclear).

### `google-data-agent (LATEST_GA_MODEL)`

Scored on all 1 runs of every case; runs finished: native-context-bare 288 of 96; model responses spent: native-context-bare 306.

| | `native-context-bare` |
|---|---|
| Accuracy | 90.6% |
| Confident-wrong | 5.2% |
| pass^1 | 90.6% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (67) accuracy | 97.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 75.9% |

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `native-context-bare` `bet_cart_to_checkout_minutes` run 3 turn 1: not judged yet

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on all 1 runs of every case; runs finished: native-context-bare 288 of 96; model responses spent: native-context-bare 306.

| | `native-context-bare` |
|---|---|
| Accuracy | 94.8% |
| Confident-wrong | 1.0% |
| pass^1 | 94.8% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (67) accuracy | 97.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 89.7% |

Turns still unclear after judging (counted as wrong):

- `native-context-bare` `returns_one_day` run 3 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `native-context-bare` `bet_p90_order` run 2 turn 1: not judged yet

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on all 1 runs of every case; runs finished: native-context-bare 288 of 96; model responses spent: native-context-bare 306.

| | `native-context-bare` |
|---|---|
| Accuracy | 89.6% |
| Confident-wrong | 5.2% |
| pass^1 | 89.6% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (67) accuracy | 97.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 72.4% |

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `native-context-bare` `bet_median_days_to_hire` run 3 turn 1: not judged yet

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, accuracy 94.8%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.135 [-0.219, -0.052], confident-wrong -0.010 [-0.031, +0.000]: not worth building (decides; 96 runs finished).
- `custom-hybrid` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.094 [-0.177, -0.010], confident-wrong +0.000 [-0.031, +0.031]: not worth building (decides; 96 runs finished).
- `custom-lightdash` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 96 cases: accuracy -0.390 [-0.537, -0.244], confident-wrong +0.098 [+0.024, +0.195]: not worth building (decides; 41 runs finished).
- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.156 [-0.240, -0.073], confident-wrong +0.021 [-0.021, +0.062]: not worth building (the check; 96 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.177 [-0.271, -0.083], confident-wrong +0.021 [-0.021, +0.062]: not worth building (the check; 96 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.521 [-0.625, -0.417], confident-wrong +0.010 [-0.021, +0.052]: not worth building (the check; 96 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.031 [-0.094, +0.031], confident-wrong +0.021 [-0.021, +0.062]: not worth building (the check; 96 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.188 [-0.281, -0.104], confident-wrong +0.000 [-0.031, +0.031]: not worth building (the check; 96 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.531 [-0.635, -0.427], confident-wrong +0.021 [-0.021, +0.062]: not worth building (the check; 96 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy +0.010 [-0.031, +0.052], confident-wrong -0.010 [-0.031, +0.000]: not worth building (the check; 96 runs finished).
- `custom-metricflow` (rung 4) on `claude-opus-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.188 [-0.281, -0.104], confident-wrong +0.010 [-0.021, +0.042]: not worth building (the check; 96 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.281 [-0.385, -0.188], confident-wrong +0.042 [+0.000, +0.094]: not worth building (the check; 96 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.240 [-0.333, -0.146], confident-wrong +0.000 [-0.031, +0.031]: not worth building (the check; 96 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.240 [-0.333, -0.146], confident-wrong +0.031 [-0.010, +0.073]: not worth building (the check; 96 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.219 [-0.312, -0.125], confident-wrong +0.021 [-0.021, +0.062]: not worth building (the check; 96 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.208 [-0.302, -0.125], confident-wrong +0.021 [-0.021, +0.062]: not worth building (the check; 96 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 20 of 96 cases: accuracy -0.250 [-0.450, -0.100], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 20 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-hybrid`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow`: the same verdict on every model, so the gap is not the model's.

### Errors

- No answer: the model call failed (litellm.APIError: APIError: OpenrouterException - Response payload is not completed: <TransferEncodingError: 400, message='Not enough data to satisfy transfer length header.'> LiteLLM Retried: 2 times).

## Every arm on the hard set

Written 2026-11-05T00:28Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl) and each live arm's `eval-hard-<arm>.jsonl` under [the rule](RULE.md): 43 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 1 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
129 of `baseline`'s 129 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `claude-haiku-5-5`

Scored on all 1 runs of every case; runs finished: baseline 129 of 43, custom-metricflow 129 of 43, custom-hybrid 129 of 43, custom-toolbox 129 of 43, native-mcp 129 of 43; model responses spent: baseline 510, custom-metricflow 437, custom-hybrid 480, custom-toolbox 259, native-mcp 662.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 58.1% | 72.1% | 83.7% | 46.5% | 83.7% |
| Confident-wrong | 11.6% | 11.6% | 2.3% | 4.7% | 4.7% |
| pass^1 | 58.1% | 72.1% | 83.7% | 46.5% | 83.7% |
| `conversation` (8) accuracy | 50.0% | 62.5% | 62.5% | 25.0% | 50.0% |
| `covered` (24) accuracy | 66.7% | 87.5% | 87.5% | 58.3% | 79.2% |
| `trap` (6) accuracy | 50.0% | 100.0% | 100.0% | 66.7% | 100.0% |
| `uncovered` (19) accuracy | 47.4% | 52.6% | 78.9% | 31.6% | 89.5% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.140 [+0.000, +0.302]: no difference.
- Confident-wrong: +0.000 [-0.140, +0.140]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 6 (0 the code left unclear, 6 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 6 of 6 (2 to wrong, hedged; 4 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_candidates_still_in_running` run 1 turn 1: right / right
- `baseline` `hard_candidates_still_in_running` run 3 turn 1: right / wrong
- `baseline` `hard_revenue_per_session` run 3 turn 1: wrong / right
- `custom-metricflow` `hard_candidates_still_in_running` run 2 turn 1: right / right
- `custom-toolbox` `hard_best_customer_september` run 2 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `native-mcp` `hard_replies_within_12_hours` run 2 turn 1: not judged yet

### `claude-sonnet-5-5`

Scored on all 1 runs of every case; runs finished: custom-metricflow 129 of 43, custom-toolbox 129 of 43, native-mcp 87 of 43; model responses spent: custom-metricflow 445, custom-toolbox 257, native-mcp 403.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 55.8% | 48.8% | 90.7% |
| Confident-wrong | 7.0% | 7.0% | 0.0% |
| pass^1 | 55.8% | 48.8% | 90.7% |
| `conversation` (8) accuracy | 62.5% | 37.5% | 50.0% |
| `covered` (24) accuracy | 83.3% | 62.5% | 83.3% |
| `trap` (6) accuracy | 100.0% | 66.7% | 100.0% |
| `uncovered` (19) accuracy | 21.1% | 31.6% | 100.0% |

Turns judged: 3 (1 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 2 of 2 (1 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `hard_candidates_still_in_running` run 1 turn 1: wrong / confident-wrong
- `custom-toolbox` `hard_august_signups_bought` run 3 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-toolbox` `hard_budget_pacing` run 1 turn 1: not judged yet
- `custom-toolbox` `hard_budget_pacing` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_budget_pacing` run 3 turn 1: not judged yet
- `custom-toolbox` `hard_gmv_september` run 1 turn 1: not judged yet
- `custom-toolbox` `hard_gmv_september` run 2 turn 1: not judged yet
- `custom-toolbox` `hard_gmv_september` run 3 turn 1: not judged yet

### `nvidia/nemotron-3.5-super-vl:free`

Scored on all 1 runs of every case; runs finished: custom-metricflow 129 of 43; model responses spent: custom-metricflow 502.

| | `custom-metricflow` |
|---|---|
| Accuracy | 72.1% |
| Confident-wrong | 9.3% |
| pass^1 | 72.1% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (24) accuracy | 83.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 57.9% |

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

### `claude-code (haiku)`

Scored on all 1 runs of every case; runs finished: cc-metricflow 43 of 43; model responses spent: cc-metricflow 47.

| | `cc-metricflow` |
|---|---|
| Accuracy | 44.2% |
| Confident-wrong | 18.6% |
| pass^1 | 44.2% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (24) accuracy | 79.2% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 0.0% |

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_ad_spend_wow` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_cart_abandonment` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_refund_rate_by_value` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_repeat_rate_october` run 1 turn 1: not judged yet
- `cc-metricflow` `hard_revenue_per_buyer_country` run 1 turn 1: not judged yet

### `claude-code (sonnet)`

Scored on all 1 runs of every case; runs finished: cc-metricflow 43 of 43; model responses spent: cc-metricflow 47.

| | `cc-metricflow` |
|---|---|
| Accuracy | 51.2% |
| Confident-wrong | 30.2% |
| pass^1 | 51.2% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (24) accuracy | 91.7% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 0.0% |

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_first_time_vs_returning` run 1 turn 1: not judged yet

### `claude-code (opus)`

Scored on all 1 runs of every case; runs finished: cc-metricflow 43 of 43; model responses spent: cc-metricflow 47.

| | `cc-metricflow` |
|---|---|
| Accuracy | 53.5% |
| Confident-wrong | 25.6% |
| pass^1 | 53.5% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (24) accuracy | 91.7% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 5.3% |

### `claude-code (fresh-haiku)`

Scored on all 1 runs of every case; runs finished: cc-metricflow 129 of 43; model responses spent: cc-metricflow 141.

| | `cc-metricflow` |
|---|---|
| Accuracy | 58.1% |
| Confident-wrong | 4.7% |
| pass^1 | 58.1% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (24) accuracy | 91.7% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 15.8% |

### `claude-code (fresh-sonnet)`

Scored on all 1 runs of every case; runs finished: cc-metricflow 129 of 43; model responses spent: cc-metricflow 141.

| | `cc-metricflow` |
|---|---|
| Accuracy | 48.8% |
| Confident-wrong | 11.6% |
| pass^1 | 48.8% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (24) accuracy | 83.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 5.3% |

### `claude-code (fresh-opus)`

Scored on all 1 runs of every case; runs finished: cc-metricflow 43 of 43; model responses spent: cc-metricflow 47.

| | `cc-metricflow` |
|---|---|
| Accuracy | 51.2% |
| Confident-wrong | 9.3% |
| pass^1 | 51.2% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (24) accuracy | 83.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 10.5% |

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `cc-metricflow` `hard_refund_rate_by_value` run 1 turn 1: not judged yet

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on all 1 runs of every case; runs finished: native-bare 129 of 43, native-context-bare 129 of 43, native-context 129 of 43, native-governed 129 of 43, native-graph 129 of 43, native-kc-max 128 of 43, native-kc-reach 129 of 43, native-kc 129 of 43, native-shaped 129 of 43; model responses spent: native-bare 141, native-context-bare 141, native-context 142, native-governed 141, native-graph 141, native-kc-max 138, native-kc-reach 141, native-kc 141, native-shaped 141.

| | `native-bare` | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 62.8% | 90.7% | 90.7% | 72.1% | 55.8% | 86.0% | 83.7% | 62.8% | 60.5% |
| Confident-wrong | 32.6% | 0.0% | 0.0% | 0.0% | 18.6% | 2.3% | 9.3% | 14.0% | 14.0% |
| pass^1 | 62.8% | 90.7% | 90.7% | 72.1% | 55.8% | 86.0% | 83.7% | 62.8% | 60.5% |
| `conversation` (8) accuracy | 62.5% | 50.0% | 50.0% | 62.5% | 50.0% | 37.5% | 62.5% | 50.0% | 37.5% |
| `covered` (24) accuracy | 62.5% | 83.3% | 83.3% | 87.5% | 62.5% | 79.2% | 83.3% | 66.7% | 54.2% |
| `trap` (6) accuracy | 50.0% | 100.0% | 100.0% | 100.0% | 33.3% | 100.0% | 83.3% | 50.0% | 50.0% |
| `uncovered` (19) accuracy | 63.2% | 100.0% | 100.0% | 52.6% | 47.4% | 94.7% | 84.2% | 57.9% | 68.4% |

Turns judged: 12 (7 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 12.
Confident-wrong turns the judge moved: 1 of 5 (1 to wrong, hedged; 0 to unclear).

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `native-bare` `hard_ambiguous_q3` run 3 turn 1: not judged yet
- `native-bare` `hard_aov_last_month` run 3 turn 1: not judged yet

### `google-data-agent (LATEST_GA_MODEL)`

Scored on partial: 1 run(s) of 42 of 43 cases; runs finished: native-context-bare 128 of 43; model responses spent: native-context-bare 140.

| | `native-context-bare` |
|---|---|
| Accuracy | 92.9% |
| Confident-wrong | 2.4% |
| pass^1 | 92.9% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (23) accuracy | 91.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 94.7% |

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `native-context-bare` `hard_candidates_still_in_running` run 1 turn 1: not judged yet

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on all 1 runs of every case; runs finished: native-context-bare 128 of 43; model responses spent: native-context-bare 140.

| | `native-context-bare` |
|---|---|
| Accuracy | 95.3% |
| Confident-wrong | 0.0% |
| pass^1 | 95.3% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (24) accuracy | 91.7% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 100.0% |

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on all 1 runs of every case; runs finished: native-context-bare 128 of 43; model responses spent: native-context-bare 140.

| | `native-context-bare` |
|---|---|
| Accuracy | 95.3% |
| Confident-wrong | 0.0% |
| pass^1 | 95.3% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (24) accuracy | 91.7% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 100.0% |

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, accuracy 95.3%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.233 [-0.372, -0.116], confident-wrong +0.116 [+0.023, +0.209]: not worth building (the check; 43 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.116 [-0.209, -0.023], confident-wrong +0.023 [+0.000, +0.070]: not worth building (the check; 43 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.488 [-0.628, -0.349], confident-wrong +0.047 [+0.000, +0.116]: not worth building (the check; 43 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.116 [-0.209, -0.023], confident-wrong +0.047 [+0.000, +0.116]: not worth building (the check; 43 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.395 [-0.558, -0.256], confident-wrong +0.070 [+0.000, +0.163]: not worth building (the check; 43 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.465 [-0.605, -0.326], confident-wrong +0.070 [+0.000, +0.163]: not worth building (the check; 43 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.047 [-0.116, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 43 runs finished).
- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.233 [-0.372, -0.116], confident-wrong +0.093 [+0.023, +0.186]: not worth building (decides; 43 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.512 [-0.651, -0.372], confident-wrong +0.186 [+0.070, +0.302]: not worth building (the check; 43 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.442 [-0.581, -0.302], confident-wrong +0.302 [+0.163, +0.442]: not worth building (the check; 43 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.419 [-0.558, -0.279], confident-wrong +0.256 [+0.140, +0.395]: not worth building (the check; 43 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.372 [-0.512, -0.233], confident-wrong +0.047 [+0.000, +0.116]: not worth building (the check; 43 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.465 [-0.605, -0.326], confident-wrong +0.116 [+0.023, +0.209]: not worth building (the check; 43 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.442 [-0.581, -0.302], confident-wrong +0.093 [+0.023, +0.186]: not worth building (the check; 43 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow`: the same verdict on every model, so the gap is not the model's.

### The rule on both sets

RULE.md § Changes since freezing (#356): each set goes through the rule on its own; an arm of ours is worth building only if step 2 holds on both sets, and where they disagree the cheaper rung wins, as a tie does.
- The managed best on the frozen set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 94.8%.
- The managed best on the hard set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 95.3%.
- `custom-metricflow` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-hybrid` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-lightdash` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-metricflow` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-hybrid` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-toolbox` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `native-mcp` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-metricflow` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-toolbox` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `native-mcp` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-metricflow` on `claude-opus-5-5` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `cc-metricflow` on `claude-code (haiku)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (sonnet)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (opus)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-haiku)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-sonnet)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-opus)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- Step 3 (RULE.md § The rule, 3; it applies when no arm of ours is worth building): the arms with no accuracy difference from the managed best on both sets: `native-mcp` on `claude-sonnet-5-5` (rung 3), `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)` (rung 1).
  The cheapest rung among them is 1: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`; within a rung the arm with fewer moving parts named in its finding wins (§ The cost ladder), which the report names.
