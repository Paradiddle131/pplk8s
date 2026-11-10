# The bet's local arms on the hard set

Written 2026-11-10T00:15Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl), the log of every run, under [the rule](RULE.md): 40 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `claude -p (haiku)` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
141 of `baseline`'s 141 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

## `claude-haiku-5-5`

Scored on partial: 1 run(s) of 40 of 40 cases; runs finished: baseline 118 of 120, custom-metricflow 120 of 120, custom-hybrid 120 of 120; model responses spent: baseline 467, custom-metricflow 407, custom-hybrid 449.

| | `baseline` | `custom-metricflow` | `custom-hybrid` |
|---|---|---|---|
| Accuracy | 60.0% | 72.5% | 85.0% |
| Confident-wrong | 10.0% | 5.0% | 2.5% |
| pass^1 | 60.0% | 72.5% | 85.0% |
| `conversation` (7) accuracy | 57.1% | 71.4% | 71.4% |
| `covered` (21) accuracy | 71.4% | 90.5% | 90.5% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% |
| `uncovered` (19) accuracy | 47.4% | 52.6% | 78.9% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.125 [-0.025, +0.275]: no difference.
- Confident-wrong: -0.050 [-0.150, +0.050]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 4 (`custom-metricflow` 4 confident-wrong to wrong).

Turns judged: 7 (0 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 5.
Confident-wrong turns the judge moved: 7 of 7 (5 to wrong, hedged; 2 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_revenue_per_session` run 3 turn 1: right / wrong
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

Scored on all 3 runs of every case; runs finished: custom-metricflow 120 of 120; model responses spent: custom-metricflow 412.

| | `custom-metricflow` |
|---|---|
| Accuracy | 56.7% |
| Confident-wrong | 1.7% |
| pass^3 | 55.0% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (21) accuracy | 85.7% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 24.6% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 6 (`custom-metricflow` 6 confident-wrong to wrong).

Turns judged: 2 (1 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 1 of 1 (1 to wrong, hedged; 0 to unclear).

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-metricflow` `hard_candidates_still_in_running` run 3 turn 1: not judged yet

## `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 23 of 40 cases; runs finished: baseline 23 of 120, custom-metricflow 120 of 120, custom-hybrid 23 of 120; model responses spent: baseline 105, custom-metricflow 468, custom-hybrid 90.

| | `baseline` | `custom-metricflow` | `custom-hybrid` |
|---|---|---|---|
| Accuracy | 69.6% | 82.6% | 91.3% |
| Confident-wrong | 13.0% | 4.3% | 0.0% |
| pass^1 | 69.6% | 82.6% | 91.3% |
| `conversation` (5) accuracy | 20.0% | 60.0% | 60.0% |
| `covered` (16) accuracy | 68.8% | 81.2% | 87.5% |
| `trap` (4) accuracy | 75.0% | 100.0% | 100.0% |
| `uncovered` (7) accuracy | 71.4% | 85.7% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.130 [-0.087, +0.348]: no difference.
- Confident-wrong: -0.087 [-0.261, +0.087]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 1 (`baseline` 1 unclear to confident-wrong).

Turns judged: 4 (1 the code left unclear, 3 confident-wrong with a hedge outside the list); verdicts that stood: 3.
Confident-wrong turns the judge moved: 2 of 3 (1 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_cost_per_booking_rise` run 1 turn 1: right / right

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-metricflow` `hard_august_signups_bought` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_candidates_still_in_running` run 2 turn 1: not judged yet
