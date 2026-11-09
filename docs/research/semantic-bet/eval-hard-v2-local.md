# The bet's local arms on the hard set v2

Written 2026-11-09T12:04Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-v2-local.jsonl`](eval-hard-v2-local.jsonl), the log of every run, under [the rule](RULE.md): 54 cases of `services/semantic-agent/evals/semantic_bet_hard_v2.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `claude -p (haiku)` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
223 of `baseline`'s 223 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

## `claude-haiku-5-5`

Scored on partial: 1 run(s) of 40 of 54 cases; runs finished: baseline 118 of 162, custom-metricflow 120 of 162, custom-hybrid 120 of 162; model responses spent: baseline 467, custom-metricflow 407, custom-hybrid 449.

| | `baseline` | `custom-metricflow` | `custom-hybrid` |
|---|---|---|---|
| Accuracy | 60.0% | 72.5% | 85.0% |
| Confident-wrong | 10.0% | 5.0% | 2.5% |
| pass^1 | 60.0% | 72.5% | 85.0% |
| `composable` (14) accuracy | 64.3% | 64.3% | 92.9% |
| `conversation` (7) accuracy | 57.1% | 71.4% | 71.4% |
| `covered` (21) accuracy | 71.4% | 90.5% | 90.5% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% |
| `uncovered` (5) accuracy | 0.0% | 20.0% | 40.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.125 [-0.025, +0.275]: no difference.
- Confident-wrong: -0.050 [-0.150, +0.050]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 4 (`custom-metricflow` 4 confident-wrong to wrong).

Turns judged: 7 (0 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 5.
Confident-wrong turns the judge moved: 7 of 7 (5 to wrong, hedged; 2 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_basket_size_week` run 1 turn 1: confident-wrong / wrong
- `custom-metricflow` `hard_weekend_vs_weekday` run 1 turn 1: right / right

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `baseline` `hard_candidates_still_in_running` run 1 turn 1: not judged yet
- `baseline` `hard_candidates_still_in_running` run 3 turn 1: not judged yet
- `baseline` `hard_repeat_rate_october` run 2 turn 1: not judged yet
- `custom-hybrid` `hard_august_signups_bought` run 3 turn 1: not judged yet
- `custom-hybrid` `hard_candidates_still_in_running` run 1 turn 1: not judged yet
- `custom-hybrid` `hard_candidates_still_in_running` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_august_signups_bought` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_august_signups_bought` run 3 turn 1: not judged yet
- `custom-metricflow` `hard_candidates_still_in_running` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_candidates_still_in_running` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_repeat_rate_october` run 3 turn 1: not judged yet

## `claude-sonnet-5-5`

Scored on partial: 1 run(s) of 40 of 54 cases; runs finished: custom-metricflow 120 of 162; model responses spent: custom-metricflow 412.

| | `custom-metricflow` |
|---|---|
| Accuracy | 55.0% |
| Confident-wrong | 2.5% |
| pass^1 | 55.0% |
| `composable` (14) accuracy | 21.4% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (21) accuracy | 85.7% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (5) accuracy | 20.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 6 (`custom-metricflow` 6 confident-wrong to wrong).

Turns judged: 2 (1 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 1 of 1 (1 to wrong, hedged; 0 to unclear).

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-metricflow` `hard_candidates_still_in_running` run 3 turn 1: not judged yet

## `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 26 of 54 cases; runs finished: baseline 105 of 162, custom-metricflow 162 of 162, custom-hybrid 78 of 162, custom-metricflow-compute 162 of 162; model responses spent: baseline 516, custom-metricflow 616, custom-hybrid 304, custom-metricflow-compute 598.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-metricflow-compute` |
|---|---|---|---|---|
| Accuracy | 73.1% | 84.6% | 92.3% | 88.5% |
| Confident-wrong | 11.5% | 3.8% | 0.0% | 0.0% |
| pass^1 | 73.1% | 84.6% | 92.3% | 88.5% |
| `composable` (9) accuracy | 77.8% | 88.9% | 100.0% | 88.9% |
| `conversation` (5) accuracy | 20.0% | 60.0% | 60.0% | 60.0% |
| `covered` (17) accuracy | 70.6% | 82.4% | 88.2% | 88.2% |
| `trap` (4) accuracy | 75.0% | 100.0% | 100.0% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.115 [-0.077, +0.308]: no difference.
- Confident-wrong: -0.077 [-0.231, +0.077]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 5 (`baseline` 1 unclear to confident-wrong; `custom-hybrid` 1 unclear to wrong; `custom-metricflow` 1 unclear to confident-wrong; `custom-metricflow-compute` 1 unclear to confident-wrong; `custom-metricflow-compute` 1 unclear to wrong).

Turns judged: 11 (3 the code left unclear, 8 confident-wrong with a hedge outside the list); verdicts that stood: 8.
Confident-wrong turns the judge moved: 5 of 8 (2 to wrong, hedged; 3 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_cost_per_booking_rise` run 1 turn 1: right / right
- `custom-metricflow` `hv2_signups_never_ordered` run 1 turn 1: right / right
- `custom-metricflow-compute` `hard_cost_per_booking_rise` run 1 turn 1: right / right

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-metricflow` `hard_august_signups_bought` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_candidates_still_in_running` run 2 turn 1: not judged yet
