# Every arm on the bet's sets

Each set is scored on its own under [the rule](RULE.md), with its own comparison against the managed best: [the frozen set](#every-arm-on-the-frozen-set), then [the hard set](#every-arm-on-the-hard-set) (#356, #364).

## Every arm on the frozen set

Written 2026-11-03T23:09Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
0 of `baseline`'s 336 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 41 of 96 cases; runs finished: baseline 48 of 288, custom-metricflow 47 of 288, custom-lightdash 41 of 288; model responses spent: baseline 221, custom-metricflow 179, custom-lightdash 77.

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

Turns judged: 7 (2 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 7.
Confident-wrong turns the judge moved: 3 of 5 (3 to wrong, hedged; 0 to unclear).

### `claude-haiku-5-5`

Scored on all 3 runs of every case; runs finished: baseline 288 of 288, custom-metricflow 288 of 288; model responses spent: baseline 1038, custom-metricflow 962.

| | `baseline` | `custom-metricflow` |
|---|---|---|
| Accuracy | 61.1% | 77.8% |
| Confident-wrong | 10.4% | 2.4% |
| pass^3 | 56.2% | 71.9% |
| `conversation` (7) accuracy | 57.1% | 95.2% |
| `covered` (67) accuracy | 71.6% | 92.5% |
| `distractor` (3) accuracy | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% |
| `trap` (11) accuracy | 66.7% | 97.0% |
| `uncovered` (29) accuracy | 36.8% | 43.7% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.167 [+0.069, +0.264]: a difference.
- Confident-wrong: -0.080 [-0.139, -0.024]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns still unclear after judging (counted as wrong):

- `baseline` `bet_most_email_opens` run 3 turn 1: not judged yet
- `custom-metricflow` `active_customers` run 3 turn 1: not judged yet
- `custom-metricflow` `cancelled_total` run 2 turn 1: not judged yet
- `custom-metricflow` `cancelled_total` run 3 turn 1: not judged yet
- `custom-metricflow` `candidates_in_interview_as_of` run 1 turn 1: not judged yet
- `custom-metricflow` `engaged_customers_week` run 2 turn 1: not judged yet
- `custom-metricflow` `orders_over_100` run 2 turn 1: not judged yet
- `custom-metricflow` `orders_over_100` run 3 turn 1: not judged yet
- `custom-metricflow` `partners_engaged_one_day` run 1 turn 1: not judged yet
- `custom-metricflow` `partners_engaged_one_day` run 2 turn 1: not judged yet
- `custom-metricflow` `partners_engaged_one_day` run 3 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `baseline` `damaged_returns` run 1 turn 1: not judged yet
- `baseline` `damaged_returns` run 2 turn 1: not judged yet
- `baseline` `damaged_returns` run 3 turn 1: not judged yet
- `baseline` `partners_engaged_one_day` run 3 turn 1: not judged yet
- `baseline` `return_rate_september` run 1 turn 1: not judged yet
- `baseline` `return_rate_september` run 2 turn 1: not judged yet
- `baseline` `revenue_fiscal_q3` run 3 turn 1: not judged yet
- `baseline` `shipped_orders` run 2 turn 1: not judged yet
- `baseline` `shipped_orders` run 3 turn 1: not judged yet
- `baseline` `signups_september` run 1 turn 1: not judged yet
- `baseline` `signups_september` run 2 turn 1: not judged yet
- `baseline` `signups_september` run 3 turn 1: not judged yet

### `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 288 of 288; model responses spent: custom-metricflow 931.

| | `custom-metricflow` |
|---|---|
| Accuracy | 74.0% |
| Confident-wrong | 1.4% |
| pass^3 | 69.8% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 98.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 18.4% |

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `bet_median_order_september` run 1 turn 1: not judged yet
- `custom-metricflow` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
- `custom-metricflow` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `custom-metricflow` `bet_peak_page_view_hour` run 1 turn 1: not judged yet
- `custom-metricflow` `bet_peak_page_view_hour` run 2 turn 1: not judged yet
- `custom-metricflow` `bet_peak_page_view_hour` run 3 turn 1: not judged yet
- `custom-metricflow` `orders_over_100` run 2 turn 1: not judged yet
- `custom-metricflow` `partners_engaged_one_day` run 2 turn 1: not judged yet

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on all 3 runs of every case; runs finished: native-context-bare 288 of 288, native-context 288 of 288, native-governed 288 of 288, native-graph 288 of 288, native-kc-reach 288 of 288, native-kc 288 of 288, native-shaped 288 of 288; model responses spent: native-context-bare 306, native-context 306, native-governed 306, native-graph 306, native-kc-reach 306, native-kc 306, native-shaped 306.

| | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|
| Accuracy | 89.6% | 87.2% | 72.9% | 61.8% | 86.8% | 64.2% | 61.8% |
| Confident-wrong | 4.5% | 5.2% | 1.0% | 6.9% | 6.9% | 4.2% | 5.2% |
| pass^3 | 87.5% | 83.3% | 70.8% | 57.3% | 83.3% | 59.4% | 58.3% |
| `conversation` (7) accuracy | 71.4% | 66.7% | 71.4% | 42.9% | 33.3% | 52.4% | 33.3% |
| `covered` (67) accuracy | 97.0% | 94.0% | 91.0% | 68.7% | 87.6% | 71.1% | 66.7% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 88.9% | 77.8% |
| `planted` (4) accuracy | 100.0% | 100.0% | 66.7% | 83.3% | 100.0% | 100.0% | 100.0% |
| `trap` (11) accuracy | 100.0% | 100.0% | 100.0% | 63.6% | 87.9% | 63.6% | 51.5% |
| `uncovered` (29) accuracy | 72.4% | 71.3% | 31.0% | 46.0% | 85.1% | 48.3% | 50.6% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 6 (`native-governed` 1 confident-wrong to wrong; `native-governed` 2 unclear to declined; `native-shaped` 1 confident-wrong to wrong; `native-shaped` 2 unclear to declined).

Turns judged: 16 (14 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 16.
Confident-wrong turns the judge moved: 1 of 2 (1 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `native-context` `customers_to_date` run 3 turn 1: not judged yet
- `native-context` `followup_day_before` run 3 turn 2: not judged yet
- `native-context` `leads_mtd` run 3 turn 1: not judged yet
- `native-governed` `bet_customers_over_three_orders` run 2 turn 1: not judged yet
- `native-governed` `bet_most_email_opens` run 3 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `native-context` `bet_median_days_to_hire` run 2 turn 1: not judged yet
- `native-context` `bet_median_reply_hours` run 3 turn 1: not judged yet
- `native-context-bare` `bet_median_reply_hours` run 3 turn 1: not judged yet

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, accuracy 89.6%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 47 of 96 cases: accuracy -0.021 [-0.064, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 47 runs finished).
- `custom-lightdash` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 41 of 96 cases: accuracy -0.390 [-0.537, -0.244], confident-wrong +0.098 [+0.024, +0.195]: not worth building (decides; 41 runs finished).
- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy -0.118 [-0.188, -0.049], confident-wrong -0.021 [-0.069, +0.021]: not worth building (the check; 288 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy -0.156 [-0.236, -0.080], confident-wrong -0.031 [-0.076, +0.010]: not worth building (the check; 288 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.

## Every arm on the hard set

Written 2026-11-03T23:09Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl) and each live arm's `eval-hard-<arm>.jsonl` under [the rule](RULE.md): 43 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on all 3 runs of every case; runs finished: native-context 129 of 129, native-governed 129 of 129, native-kc 129 of 129; model responses spent: native-context 142, native-governed 141, native-kc 141.

| | `native-context` | `native-governed` | `native-kc` |
|---|---|---|---|
| Accuracy | 92.2% | 69.8% | 63.6% |
| Confident-wrong | 0.0% | 1.6% | 13.2% |
| pass^3 | 90.7% | 62.8% | 55.8% |
| `conversation` (8) accuracy | 58.3% | 66.7% | 54.2% |
| `covered` (24) accuracy | 86.1% | 86.1% | 66.7% |
| `trap` (6) accuracy | 100.0% | 100.0% | 50.0% |
| `uncovered` (19) accuracy | 100.0% | 49.1% | 59.6% |

Turns still unclear after judging (counted as wrong):

- `native-governed` `hard_repeat_rate_october` run 3 turn 1: not judged yet
- `native-kc` `hard_replies_within_12_hours` run 2 turn 1: not judged yet

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`, accuracy 92.2%.
No arm of ours (rung 3 or 4) is logged on any model: nothing to compare.

### The rule on both sets

RULE.md § Changes since freezing (#356): each set goes through the rule on its own; an arm of ours is worth building only if step 2 holds on both sets, and where they disagree the cheaper rung wins, as a tie does.
- The managed best on the frozen set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 89.6%.
- The managed best on the hard set: `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`, 92.2%.
It cannot apply yet: no arm of ours (rung 3 or 4) is logged on the hard set, so step 2 has not run on both sets; each set's own verdict above is provisional.
- `custom-metricflow` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-lightdash` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-metricflow` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-metricflow` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
Step 3 (the cheapest arm with no accuracy difference from the best on both sets) is read in the report, not computed here.
