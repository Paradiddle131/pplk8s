# The bet's local arms on the frozen set

Written 2026-11-03T22:06Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl), the log of every run, under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
0 of `baseline`'s 336 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

## `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 47 of 96 cases; runs finished: baseline 48 of 288, custom-metricflow 47 of 288; model responses spent: baseline 221, custom-metricflow 179.

| | `baseline` | `custom-metricflow` |
|---|---|---|
| Accuracy | 68.1% | 95.7% |
| Confident-wrong | 12.8% | 0.0% |
| pass^1 | 68.1% | 95.7% |
| `covered` (45) accuracy | 68.9% | 100.0% |
| `distractor` (2) accuracy | 100.0% | 100.0% |
| `trap` (8) accuracy | 50.0% | 100.0% |
| `uncovered` (2) accuracy | 50.0% | 0.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.277 [+0.128, +0.426]: a difference.
- Confident-wrong: -0.128 [-0.234, -0.043]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 2 (0 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 0 of 2 (0 to wrong, hedged; 0 to unclear).

## `claude-haiku-5-5`

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

## `claude-sonnet-5-5`

Scored on partial: 1 run(s) of 96 of 96 cases; runs finished: custom-metricflow 170 of 288; model responses spent: custom-metricflow 558.

| | `custom-metricflow` |
|---|---|
| Accuracy | 76.0% |
| Confident-wrong | 1.0% |
| pass^1 | 76.0% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 98.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 24.1% |

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `bet_median_order_september` run 1 turn 1: not judged yet
- `custom-metricflow` `bet_peak_page_view_hour` run 1 turn 1: not judged yet
- `custom-metricflow` `bet_peak_page_view_hour` run 2 turn 1: not judged yet
- `custom-metricflow` `orders_over_100` run 2 turn 1: not judged yet
- `custom-metricflow` `partners_engaged_one_day` run 2 turn 1: not judged yet
