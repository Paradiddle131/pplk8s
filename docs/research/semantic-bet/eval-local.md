# The bet's local arms on the frozen set

Written 2026-11-04T19:56Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl), the log of every run, under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
0 of `baseline`'s 336 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

## `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 48 of 96 cases; runs finished: baseline 48 of 288, custom-metricflow 110 of 288; model responses spent: baseline 221, custom-metricflow 409.

| | `baseline` | `custom-metricflow` |
|---|---|---|
| Accuracy | 68.8% | 95.8% |
| Confident-wrong | 12.5% | 0.0% |
| pass^1 | 68.8% | 95.8% |
| `covered` (46) accuracy | 69.6% | 100.0% |
| `distractor` (2) accuracy | 100.0% | 100.0% |
| `trap` (8) accuracy | 50.0% | 100.0% |
| `uncovered` (2) accuracy | 50.0% | 0.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.271 [+0.125, +0.417]: a difference.
- Confident-wrong: -0.125 [-0.229, -0.042]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 4 (2 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 4.
Confident-wrong turns the judge moved: 0 of 2 (0 to wrong, hedged; 0 to unclear).

## `claude-haiku-5-5`

Scored on all 3 runs of every case; runs finished: baseline 288 of 288, custom-metricflow 288 of 288, custom-hybrid 288 of 288; model responses spent: baseline 1038, custom-metricflow 962, custom-hybrid 1052.

| | `baseline` | `custom-metricflow` | `custom-hybrid` |
|---|---|---|---|
| Accuracy | 61.1% | 81.2% | 75.7% |
| Confident-wrong | 6.6% | 2.4% | 4.2% |
| pass^3 | 56.2% | 78.1% | 72.9% |
| `conversation` (7) accuracy | 57.1% | 95.2% | 100.0% |
| `covered` (67) accuracy | 71.6% | 97.5% | 88.1% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% |
| `trap` (11) accuracy | 66.7% | 97.0% | 93.9% |
| `uncovered` (29) accuracy | 36.8% | 43.7% | 47.1% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.201 [+0.108, +0.295]: a difference.
- Confident-wrong: -0.042 [-0.090, +0.003]: no difference.

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

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-hybrid` `calls_about_returns` run 3 turn 1: not judged yet
- `custom-hybrid` `signups_september` run 2 turn 1: not judged yet
- `custom-hybrid` `signups_september` run 3 turn 1: not judged yet

## `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 288 of 288; model responses spent: custom-metricflow 931.

| | `custom-metricflow` |
|---|---|
| Accuracy | 74.7% |
| Confident-wrong | 1.4% |
| pass^3 | 71.9% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 99.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 18.4% |

Turns judged: 8 (8 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 8.

## `claude-opus-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 288 of 288; model responses spent: custom-metricflow 932.

| | `custom-metricflow` |
|---|---|
| Accuracy | 74.3% |
| Confident-wrong | 2.1% |
| pass^3 | 72.9% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 99.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 16.1% |

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `bet_istanbul_warmer` run 1 turn 1: not judged yet
- `custom-metricflow` `bet_istanbul_warmer` run 2 turn 1: not judged yet
- `custom-metricflow` `bet_istanbul_warmer` run 3 turn 1: not judged yet
- `custom-metricflow` `bet_peak_checkout_hour` run 3 turn 1: not judged yet
- `custom-metricflow` `cancelled_total` run 2 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-metricflow` `bet_peak_checkout_hour` run 2 turn 1: not judged yet
