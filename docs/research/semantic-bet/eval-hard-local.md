# The bet's local arms on the hard set

Written 2026-11-14T00:47Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl), the log of every run, under [the rule](RULE.md): 40 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `claude -p (haiku)` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
192 of `baseline`'s 192 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

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

Scored on partial: 1 run(s) of 40 of 40 cases; runs finished: baseline 74 of 120, custom-metricflow 120 of 120, custom-hybrid 74 of 120; model responses spent: baseline 371, custom-metricflow 468, custom-hybrid 320.

| | `baseline` | `custom-metricflow` | `custom-hybrid` |
|---|---|---|---|
| Accuracy | 67.5% | 72.5% | 90.0% |
| Confident-wrong | 20.0% | 10.0% | 2.5% |
| pass^1 | 67.5% | 72.5% | 90.0% |
| `conversation` (7) accuracy | 28.6% | 71.4% | 71.4% |
| `covered` (21) accuracy | 66.7% | 85.7% | 90.5% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% |
| `uncovered` (19) accuracy | 68.4% | 57.9% | 89.5% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.050 [-0.150, +0.250]: no difference.
- Confident-wrong: -0.100 [-0.250, +0.050]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 1 (`baseline` 1 unclear to confident-wrong).

Turns judged: 5 (1 the code left unclear, 4 confident-wrong with a hedge outside the list); verdicts that stood: 4.
Confident-wrong turns the judge moved: 3 of 4 (2 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_cost_per_booking_rise` run 1 turn 1: right / right

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-metricflow` `hard_august_signups_bought` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_candidates_still_in_running` run 2 turn 1: not judged yet
