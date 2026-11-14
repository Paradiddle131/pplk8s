# The bet's local arms on the frozen set

Written 2026-11-14T00:12Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl), the log of every run, under [the rule](RULE.md): 74 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `claude -p (haiku)` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
110 of `baseline`'s 352 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

## `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 74 of 74 cases; runs finished: baseline 138 of 222, custom-metricflow 87 of 222, custom-hybrid 138 of 222, custom-metricflow-compute 222 of 222; model responses spent: baseline 550, custom-metricflow 337, custom-hybrid 557, custom-metricflow-compute 833.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-metricflow-compute` |
|---|---|---|---|---|
| Accuracy | 86.5% | 91.9% | 98.6% | 91.9% |
| Confident-wrong | 5.4% | 0.0% | 1.4% | 0.0% |
| pass^1 | 86.5% | 91.9% | 98.6% | 91.9% |
| `conversation` (7) accuracy | 42.9% | 100.0% | 100.0% | 100.0% |
| `covered` (62) accuracy | 85.5% | 98.4% | 98.4% | 98.4% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% | 100.0% |
| `trap` (10) accuracy | 80.0% | 100.0% | 100.0% | 100.0% |
| `uncovered` (12) accuracy | 91.7% | 58.3% | 100.0% | 58.3% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.054 [-0.041, +0.149]: no difference.
- Confident-wrong: -0.054 [-0.108, -0.014]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 2 (`baseline` 2 unclear to confident-wrong).

Turns judged: 11 (6 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 9.
Confident-wrong turns the judge moved: 2 of 5 (0 to wrong, hedged; 2 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `bet_median_days_to_return` run 2 turn 1: right / right
- `baseline` `bet_median_signup_to_first_order` run 1 turn 1: right / right

## `claude-haiku-5-5`

Scored on partial: 1 run(s) of 71 of 74 cases; runs finished: baseline 214 of 222, custom-metricflow 222 of 222, custom-hybrid 220 of 222; model responses spent: baseline 766, custom-metricflow 745, custom-hybrid 781.

| | `baseline` | `custom-metricflow` | `custom-hybrid` |
|---|---|---|---|
| Accuracy | 63.4% | 87.3% | 81.7% |
| Confident-wrong | 5.6% | 1.4% | 4.2% |
| pass^1 | 63.4% | 87.3% | 81.7% |
| `conversation` (6) accuracy | 66.7% | 100.0% | 100.0% |
| `covered` (59) accuracy | 71.2% | 93.2% | 84.7% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% |
| `trap` (9) accuracy | 66.7% | 100.0% | 100.0% |
| `uncovered` (12) accuracy | 25.0% | 58.3% | 66.7% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.239 [+0.113, +0.366]: a difference.
- Confident-wrong: -0.042 [-0.099, +0.014]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 1 (`custom-metricflow` 1 confident-wrong to wrong).

Turns judged: 13 (0 the code left unclear, 13 confident-wrong with a hedge outside the list); verdicts that stood: 12.
Confident-wrong turns the judge moved: 12 of 13 (11 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `signups_september` run 1 turn 1: wrong / declined
- `custom-hybrid` `active_customers` run 1 turn 1: not judged yet
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

- `baseline` `objection_rate` run 3 turn 1: not judged yet
- `baseline` `outreach_reply_rate` run 1 turn 1: not judged yet
- `baseline` `outreach_reply_rate` run 2 turn 1: not judged yet
- `baseline` `outreach_reply_rate` run 3 turn 1: not judged yet
- `baseline` `partners_engaged_one_day` run 3 turn 1: not judged yet
- `custom-hybrid` `calls_about_returns` run 2 turn 1: not judged yet
- `custom-hybrid` `calls_about_returns` run 3 turn 1: not judged yet
- `custom-hybrid` `signup_to_first_order_rate` run 2 turn 1: not judged yet
- `custom-hybrid` `signups_september` run 2 turn 1: not judged yet
- `custom-hybrid` `signups_september` run 3 turn 1: not judged yet
- `custom-metricflow` `calls_about_returns` run 3 turn 1: not judged yet
- `custom-metricflow` `objection_rate` run 3 turn 1: not judged yet

## `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 222 of 222; model responses spent: custom-metricflow 724.

| | `custom-metricflow` |
|---|---|
| Accuracy | 83.3% |
| Confident-wrong | 0.9% |
| pass^3 | 79.7% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (62) accuracy | 96.2% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (12) accuracy | 16.7% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 1 (`custom-metricflow` 1 confident-wrong to wrong).

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `orders_over_100` run 2 turn 1: not judged yet
- `custom-metricflow` `partners_engaged_one_day` run 2 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-metricflow` `calls_about_returns` run 1 turn 1: not judged yet
- `custom-metricflow` `calls_about_returns` run 2 turn 1: not judged yet

## `claude-opus-5-5`

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

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `cancelled_total` run 2 turn 1: not judged yet
