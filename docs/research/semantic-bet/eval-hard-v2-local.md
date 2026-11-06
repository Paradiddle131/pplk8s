# The bet's local arms on the hard set v2

Written 2026-11-06T09:40Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-v2-local.jsonl`](eval-hard-v2-local.jsonl), the log of every run, under [the rule](RULE.md): 58 cases of `services/semantic-agent/evals/semantic_bet_hard_v2.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
129 of `baseline`'s 129 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

## `claude-haiku-5-5`

Scored on partial: 1 run(s) of 43 of 58 cases; runs finished: baseline 129 of 174, custom-metricflow 129 of 174, custom-hybrid 129 of 174; model responses spent: baseline 510, custom-metricflow 437, custom-hybrid 480.

| | `baseline` | `custom-metricflow` | `custom-hybrid` |
|---|---|---|---|
| Accuracy | 58.1% | 72.1% | 83.7% |
| Confident-wrong | 11.6% | 11.6% | 2.3% |
| pass^1 | 58.1% | 72.1% | 83.7% |
| `composable` (14) accuracy | 64.3% | 64.3% | 92.9% |
| `conversation` (8) accuracy | 50.0% | 62.5% | 62.5% |
| `covered` (24) accuracy | 66.7% | 87.5% | 87.5% |
| `trap` (6) accuracy | 50.0% | 100.0% | 100.0% |
| `uncovered` (5) accuracy | 0.0% | 20.0% | 40.0% |

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

## `claude-sonnet-5-5`

Scored on partial: 1 run(s) of 43 of 58 cases; runs finished: custom-metricflow 129 of 174; model responses spent: custom-metricflow 445.

| | `custom-metricflow` |
|---|---|
| Accuracy | 55.8% |
| Confident-wrong | 7.0% |
| pass^1 | 55.8% |
| `composable` (14) accuracy | 21.4% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (24) accuracy | 83.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (5) accuracy | 20.0% |

Turns judged: 3 (1 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 2 of 2 (1 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `hard_candidates_still_in_running` run 1 turn 1: wrong / confident-wrong

## `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 43 of 58 cases; runs finished: custom-metricflow 129 of 174, custom-hybrid 43 of 174; model responses spent: custom-metricflow 502, custom-hybrid 189.

| | `custom-metricflow` | `custom-hybrid` |
|---|---|---|
| Accuracy | 72.1% | 86.0% |
| Confident-wrong | 9.3% | 0.0% |
| pass^1 | 72.1% | 86.0% |
| `composable` (14) accuracy | 71.4% | 100.0% |
| `conversation` (8) accuracy | 62.5% | 62.5% |
| `covered` (24) accuracy | 83.3% | 87.5% |
| `trap` (6) accuracy | 100.0% | 100.0% |
| `uncovered` (5) accuracy | 20.0% | 40.0% |

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.
