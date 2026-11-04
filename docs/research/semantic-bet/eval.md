# Every arm on the bet's sets

Each set is scored on its own under [the rule](RULE.md), with its own comparison against the managed best: [the frozen set](#every-arm-on-the-frozen-set), then [the hard set](#every-arm-on-the-hard-set) (#356, #364).

## Every arm on the frozen set

Written 2026-11-04T18:31Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
0 of `baseline`'s 336 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 41 of 96 cases; runs finished: baseline 48 of 288, custom-metricflow 110 of 288, custom-lightdash 41 of 288; model responses spent: baseline 221, custom-metricflow 409, custom-lightdash 77.

| | `baseline` | `custom-metricflow` | `custom-lightdash` |
|---|---|---|---|
| Accuracy | 63.4% | 95.1% | 58.5% |
| Confident-wrong | 14.6% | 0.0% | 9.8% |
| pass^1 | 63.4% | 95.1% | 58.5% |
| `covered` (39) accuracy | 64.1% | 100.0% | 61.5% |
| `distractor` (2) accuracy | 100.0% | 100.0% | 50.0% |
| `trap` (8) accuracy | 50.0% | 100.0% | 50.0% |
| `uncovered` (2) accuracy | 50.0% | 0.0% | 0.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.317 [+0.171, +0.463]: a difference.
- Confident-wrong: -0.146 [-0.268, -0.049]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 9 (4 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 9.
Confident-wrong turns the judge moved: 3 of 5 (3 to wrong, hedged; 0 to unclear).

### `claude-haiku-5-5`

Scored on partial: 1 run(s) of 42 of 96 cases; runs finished: baseline 288 of 288, custom-metricflow 288 of 288, custom-hybrid 42 of 288, custom-toolbox 288 of 288, native-mcp 288 of 288; model responses spent: baseline 1038, custom-metricflow 962, custom-hybrid 139, custom-toolbox 485, native-mcp 1383.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 64.3% | 95.2% | 81.0% | 45.2% | 92.9% |
| Confident-wrong | 9.5% | 0.0% | 4.8% | 2.4% | 4.8% |
| pass^1 | 64.3% | 95.2% | 81.0% | 45.2% | 92.9% |
| `covered` (40) accuracy | 65.0% | 100.0% | 82.5% | 47.5% | 92.5% |
| `distractor` (2) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `trap` (8) accuracy | 62.5% | 100.0% | 100.0% | 50.0% | 100.0% |
| `uncovered` (2) accuracy | 50.0% | 0.0% | 50.0% | 0.0% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.310 [+0.167, +0.452]: a difference.
- Confident-wrong: -0.095 [-0.190, -0.024]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 23 (11 the code left unclear, 12 confident-wrong with a hedge outside the list); verdicts that stood: 21.
Confident-wrong turns the judge moved: 11 of 12 (9 to wrong, hedged; 2 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `damaged_returns` run 3 turn 1: wrong / declined
- `baseline` `shipped_orders` run 3 turn 1: declined / wrong
- `custom-hybrid` `active_customers` run 1 turn 1: not judged yet
- `custom-hybrid` `cancelled_total` run 1 turn 1: not judged yet
- `custom-hybrid` `candidates_in_interview_as_of` run 1 turn 1: not judged yet
- `custom-hybrid` `engaged_customers_week` run 1 turn 1: not judged yet
- `custom-hybrid` `partners_engaged_one_day` run 1 turn 1: not judged yet
- `native-mcp` `active_customers` run 2 turn 1: not judged yet
- `native-mcp` `candidates_in_interview_as_of` run 1 turn 1: not judged yet
- `native-mcp` `partners_engaged_one_day` run 2 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `native-mcp` `bet_applicants_reaching_interview` run 2 turn 1: not judged yet
- `native-mcp` `signups_september` run 3 turn 1: not judged yet

### `claude-sonnet-5-5`

Scored on partial: 2 run(s) of 96 of 96 cases; runs finished: custom-metricflow 288 of 288, custom-toolbox 288 of 288, native-mcp 224 of 288; model responses spent: custom-metricflow 931, custom-toolbox 472, native-mcp 1002.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 74.5% | 41.7% | 95.8% |
| Confident-wrong | 1.0% | 3.1% | 0.5% |
| pass^2 | 71.9% | 40.6% | 94.8% |
| `conversation` (7) accuracy | 100.0% | 42.9% | 71.4% |
| `covered` (67) accuracy | 98.5% | 50.7% | 96.3% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 50.0% | 87.5% |
| `trap` (11) accuracy | 100.0% | 54.5% | 100.0% |
| `uncovered` (29) accuracy | 19.0% | 20.7% | 94.8% |

Turns judged: 8 (8 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 8.

Turns still unclear after judging (counted as wrong):

- `custom-toolbox` `bet_top_campaign_spend` run 2 turn 1: not judged yet
- `custom-toolbox` `signup_to_first_order_rate` run 1 turn 1: not judged yet
- `custom-toolbox` `signup_to_first_order_rate` run 3 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-toolbox` `return_rate_september` run 1 turn 1: not judged yet
- `custom-toolbox` `return_rate_september` run 2 turn 1: not judged yet
- `custom-toolbox` `revenue_fiscal_q3` run 1 turn 1: not judged yet
- `custom-toolbox` `revenue_fiscal_q3` run 3 turn 1: not judged yet

### `claude-opus-5-5`

Scored on partial: 1 run(s) of 23 of 96 cases; runs finished: custom-metricflow 23 of 288; model responses spent: custom-metricflow 75.

| | `custom-metricflow` |
|---|---|
| Accuracy | 100.0% |
| Confident-wrong | 0.0% |
| pass^1 | 100.0% |
| `covered` (23) accuracy | 100.0% |
| `trap` (1) accuracy | 100.0% |

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 48 of 96 cases; runs finished: native-bare 48 of 288, native-context-bare 288 of 288, native-context 288 of 288, native-governed 288 of 288, native-graph 288 of 288, native-kc-max 288 of 288, native-kc-reach 288 of 288, native-kc 288 of 288, native-shaped 288 of 288; model responses spent: native-bare 48, native-context-bare 306, native-context 306, native-governed 306, native-graph 306, native-kc-max 306, native-kc-reach 306, native-kc 306, native-shaped 306.

| | `native-bare` | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 75.0% | 97.9% | 95.8% | 91.7% | 64.6% | 91.7% | 87.5% | 66.7% | 66.7% |
| Confident-wrong | 22.9% | 0.0% | 0.0% | 0.0% | 8.3% | 6.2% | 10.4% | 6.2% | 6.2% |
| pass^1 | 75.0% | 97.9% | 95.8% | 91.7% | 64.6% | 91.7% | 87.5% | 66.7% | 66.7% |
| `covered` (46) accuracy | 78.3% | 100.0% | 97.8% | 93.5% | 67.4% | 93.5% | 91.3% | 69.6% | 67.4% |
| `distractor` (2) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 50.0% |
| `trap` (8) accuracy | 50.0% | 100.0% | 100.0% | 100.0% | 50.0% | 87.5% | 87.5% | 50.0% | 37.5% |
| `uncovered` (2) accuracy | 0.0% | 50.0% | 50.0% | 50.0% | 0.0% | 50.0% | 0.0% | 0.0% | 50.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 6 (`native-governed` 1 confident-wrong to wrong; `native-governed` 2 unclear to declined; `native-shaped` 1 confident-wrong to wrong; `native-shaped` 2 unclear to declined).

Turns judged: 24 (19 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 24.
Confident-wrong turns the judge moved: 1 of 5 (1 to wrong, hedged; 0 to unclear).

### `google-data-agent (LATEST_GA_MODEL)`

Scored on partial: 2 run(s) of 96 of 96 cases; runs finished: native-context-bare 248 of 288; model responses spent: native-context-bare 266.

| | `native-context-bare` |
|---|---|
| Accuracy | 90.1% |
| Confident-wrong | 5.7% |
| pass^2 | 88.5% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (67) accuracy | 97.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 74.1% |

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on partial: 1 run(s) of 1 of 96 cases; runs finished: native-context-bare 1 of 288; model responses spent: native-context-bare 1.

| | `native-context-bare` |
|---|---|
| Accuracy | 100.0% |
| Confident-wrong | 0.0% |
| pass^1 | 100.0% |
| `covered` (1) accuracy | 100.0% |
| `trap` (1) accuracy | 100.0% |

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on partial: 1 run(s) of 1 of 96 cases; runs finished: native-context-bare 1 of 288; model responses spent: native-context-bare 1.

| | `native-context-bare` |
|---|---|
| Accuracy | 100.0% |
| Confident-wrong | 0.0% |
| pass^1 | 100.0% |
| `covered` (1) accuracy | 100.0% |
| `trap` (1) accuracy | 100.0% |

### The rule across models

The managed best (RULE.md § The rule, 1): `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, accuracy 91.7%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy -0.104 [-0.198, -0.010], confident-wrong -0.049 [-0.090, -0.014]: not worth building (decides; 110 runs finished).
- `custom-lightdash` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, 41 of 96 cases: accuracy -0.325 [-0.472, -0.187], confident-wrong +0.033 [-0.049, +0.122]: not worth building (decides; 41 runs finished).
- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy -0.104 [-0.198, -0.014], confident-wrong -0.024 [-0.073, +0.017]: not worth building (the check; 288 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, 42 of 96 cases: accuracy -0.103 [-0.262, +0.048], confident-wrong -0.016 [-0.111, +0.079]: not worth building (the check; 42 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy -0.486 [-0.590, -0.382], confident-wrong -0.017 [-0.066, +0.031]: not worth building (the check; 288 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy -0.024 [-0.090, +0.042], confident-wrong -0.010 [-0.059, +0.035]: not worth building (the check; 288 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy -0.170 [-0.271, -0.069], confident-wrong -0.035 [-0.080, +0.007]: not worth building (the check; 288 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy -0.500 [-0.604, -0.392], confident-wrong -0.017 [-0.069, +0.035]: not worth building (the check; 288 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy +0.042 [-0.009, +0.097], confident-wrong -0.043 [-0.087, -0.007]: worth building (the check; 224 runs finished).
- `custom-metricflow` (rung 4) on `claude-opus-5-5` against `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, 23 of 96 cases: accuracy +0.087 [+0.000, +0.217], confident-wrong -0.087 [-0.217, +0.000]: not worth building (the check; 23 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the verdict moves with the model, so the gap is at least partly the model's.

## Every arm on the hard set

Written 2026-11-04T18:31Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl) and each live arm's `eval-hard-<arm>.jsonl` under [the rule](RULE.md): 43 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
129 of `baseline`'s 129 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `claude-haiku-5-5`

Scored on partial: 1 run(s) of 19 of 43 cases; runs finished: baseline 129 of 129, custom-metricflow 129 of 129, custom-toolbox 129 of 129, native-mcp 19 of 129; model responses spent: baseline 510, custom-metricflow 437, custom-toolbox 259, native-mcp 89.

| | `baseline` | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|
| Accuracy | 68.4% | 89.5% | 63.2% | 84.2% |
| Confident-wrong | 15.8% | 0.0% | 5.3% | 0.0% |
| pass^1 | 68.4% | 89.5% | 63.2% | 84.2% |
| `conversation` (3) accuracy | 33.3% | 33.3% | 0.0% | 33.3% |
| `covered` (19) accuracy | 68.4% | 89.5% | 63.2% | 84.2% |
| `trap` (5) accuracy | 40.0% | 100.0% | 60.0% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.211 [+0.053, +0.421]: a difference.
- Confident-wrong: -0.158 [-0.316, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 6 (0 the code left unclear, 6 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 6 of 6 (2 to wrong, hedged; 4 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_candidates_still_in_running` run 1 turn 1: right / right
- `baseline` `hard_candidates_still_in_running` run 3 turn 1: right / wrong
- `baseline` `hard_revenue_per_session` run 3 turn 1: wrong / right
- `custom-metricflow` `hard_candidates_still_in_running` run 2 turn 1: right / right
- `custom-toolbox` `hard_best_customer_september` run 2 turn 1: not judged yet

### `claude-sonnet-5-5`

Scored on partial: 1 run(s) of 43 of 43 cases; runs finished: custom-metricflow 129 of 129, custom-toolbox 44 of 129; model responses spent: custom-metricflow 445, custom-toolbox 88.

| | `custom-metricflow` | `custom-toolbox` |
|---|---|---|
| Accuracy | 55.8% | 48.8% |
| Confident-wrong | 7.0% | 7.0% |
| pass^1 | 55.8% | 48.8% |
| `conversation` (8) accuracy | 62.5% | 37.5% |
| `covered` (24) accuracy | 83.3% | 62.5% |
| `trap` (6) accuracy | 100.0% | 66.7% |
| `uncovered` (19) accuracy | 21.1% | 31.6% |

Turns judged: 3 (1 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 2 of 2 (1 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `hard_candidates_still_in_running` run 1 turn 1: wrong / confident-wrong

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-toolbox` `hard_budget_pacing` run 1 turn 1: not judged yet
- `custom-toolbox` `hard_gmv_september` run 1 turn 1: not judged yet

### `nvidia/nemotron-3.5-super-vl:free`

Scored on all 3 runs of every case; runs finished: custom-metricflow 129 of 129; model responses spent: custom-metricflow 502.

| | `custom-metricflow` |
|---|---|
| Accuracy | 73.6% |
| Confident-wrong | 7.0% |
| pass^3 | 62.8% |
| `conversation` (8) accuracy | 58.3% |
| `covered` (24) accuracy | 83.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 61.4% |

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 13 of 43 cases; runs finished: native-context-bare 129 of 129, native-context 129 of 129, native-governed 129 of 129, native-graph 129 of 129, native-kc-max 13 of 129, native-kc-reach 129 of 129, native-kc 129 of 129, native-shaped 129 of 129; model responses spent: native-context-bare 141, native-context 142, native-governed 141, native-graph 141, native-kc-max 13, native-kc-reach 141, native-kc 141, native-shaped 141.

| | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|
| Accuracy | 100.0% | 100.0% | 100.0% | 69.2% | 100.0% | 92.3% | 76.9% | 61.5% |
| Confident-wrong | 0.0% | 0.0% | 0.0% | 23.1% | 0.0% | 7.7% | 15.4% | 30.8% |
| pass^1 | 100.0% | 100.0% | 100.0% | 69.2% | 100.0% | 92.3% | 76.9% | 61.5% |
| `covered` (13) accuracy | 100.0% | 100.0% | 100.0% | 69.2% | 100.0% | 92.3% | 76.9% | 61.5% |
| `trap` (5) accuracy | 100.0% | 100.0% | 100.0% | 20.0% | 100.0% | 80.0% | 40.0% | 40.0% |

Turns judged: 12 (7 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 12.
Confident-wrong turns the judge moved: 1 of 5 (1 to wrong, hedged; 0 to unclear).

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, accuracy 93.0%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 43 of 43 cases: accuracy -0.194 [-0.318, -0.078], confident-wrong +0.093 [+0.023, +0.178]: not worth building (the check; 129 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 43 of 43 cases: accuracy -0.481 [-0.628, -0.341], confident-wrong +0.070 [+0.008, +0.147]: not worth building (the check; 129 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 19 of 43 cases: accuracy -0.070 [-0.228, +0.070], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 19 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 43 of 43 cases: accuracy -0.357 [-0.504, -0.217], confident-wrong +0.054 [+0.000, +0.124]: not worth building (the check; 129 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 43 of 43 cases: accuracy -0.442 [-0.597, -0.295], confident-wrong +0.070 [+0.000, +0.163]: not worth building (the check; 44 runs finished).
- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 43 of 43 cases: accuracy -0.194 [-0.310, -0.085], confident-wrong +0.070 [+0.023, +0.124]: not worth building (decides; 129 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.

### The rule on both sets

RULE.md § Changes since freezing (#356): each set goes through the rule on its own; an arm of ours is worth building only if step 2 holds on both sets, and where they disagree the cheaper rung wins, as a tie does.
- The managed best on the frozen set: `native-kc-max` on `google-data-agent (MODEL_UNSPECIFIED)`, 91.7%.
- The managed best on the hard set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 93.0%.
- `custom-metricflow` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-lightdash` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-metricflow` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-hybrid` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-toolbox` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `native-mcp` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-metricflow` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-toolbox` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `native-mcp` on `claude-sonnet-5-5` (the check): the frozen set: worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-metricflow` on `claude-opus-5-5` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- Step 3 (RULE.md § The rule, 3; it applies when no arm of ours is worth building): the arms with no accuracy difference from the managed best on both sets: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)` (rung 1), `native-context` on `google-data-agent (MODEL_UNSPECIFIED)` (rung 1).
  The cheapest rung among them is 1: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`; within a rung the arm with fewer moving parts named in its finding wins (§ The cost ladder), which the report names.
