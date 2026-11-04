# The bet's local arms on the hard set

Written 2026-11-04T00:13Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl), the log of every run, under [the rule](RULE.md): 43 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
129 of `baseline`'s 129 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

## `claude-haiku-5-5`

Scored on all 3 runs of every case; runs finished: baseline 129 of 129, custom-metricflow 129 of 129; model responses spent: baseline 510, custom-metricflow 437.

| | `baseline` | `custom-metricflow` |
|---|---|---|
| Accuracy | 56.6% | 73.6% |
| Confident-wrong | 11.6% | 10.1% |
| pass^3 | 51.2% | 67.4% |
| `conversation` (8) accuracy | 37.5% | 62.5% |
| `covered` (24) accuracy | 66.7% | 87.5% |
| `trap` (6) accuracy | 55.6% | 100.0% |
| `uncovered` (19) accuracy | 43.9% | 56.1% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.171 [+0.031, +0.318]: a difference.
- Confident-wrong: -0.016 [-0.116, +0.085]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `baseline` `hard_candidates_still_in_running` run 1 turn 1: not judged yet
- `baseline` `hard_candidates_still_in_running` run 3 turn 1: not judged yet
- `baseline` `hard_repeat_rate_october` run 2 turn 1: not judged yet
- `baseline` `hard_revenue_per_session` run 3 turn 1: not judged yet
- `baseline` `hard_turkish_vs_dutch_per_order` run 2 turn 1: not judged yet
- `custom-metricflow` `hard_candidates_still_in_running` run 2 turn 1: not judged yet

## `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 129 of 129; model responses spent: custom-metricflow 445.

| | `custom-metricflow` |
|---|---|
| Accuracy | 57.4% |
| Confident-wrong | 7.0% |
| pass^3 | 55.8% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (24) accuracy | 83.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 24.6% |

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `hard_mqls_social_september` run 2 turn 1: not judged yet

Confident-wrong turns with a hedge outside the list, awaiting the judge:

- `custom-metricflow` `hard_candidates_still_in_running` run 1 turn 1: not judged yet
- `custom-metricflow` `hard_candidates_still_in_running` run 3 turn 1: not judged yet
