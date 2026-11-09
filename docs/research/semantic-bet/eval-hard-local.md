# The bet's local arms on the hard set

Written 2026-11-09T02:50Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl), the log of every run, under [the rule](RULE.md): 41 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
162 of `baseline`'s 162 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

## `claude-haiku-5-5`

Scored on partial: 1 run(s) of 41 of 41 cases; runs finished: baseline 121 of 123, custom-metricflow 123 of 123, custom-hybrid 123 of 123; model responses spent: baseline 476, custom-metricflow 416, custom-hybrid 458.

| | `baseline` | `custom-metricflow` | `custom-hybrid` |
|---|---|---|---|
| Accuracy | 58.5% | 70.7% | 82.9% |
| Confident-wrong | 12.2% | 7.3% | 2.4% |
| pass^1 | 58.5% | 70.7% | 82.9% |
| `conversation` (8) accuracy | 50.0% | 62.5% | 62.5% |
| `covered` (22) accuracy | 68.2% | 86.4% | 86.4% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% |
| `uncovered` (19) accuracy | 47.4% | 52.6% | 78.9% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.122 [-0.024, +0.268]: no difference.
- Confident-wrong: -0.049 [-0.195, +0.098]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 4 (`custom-metricflow` 4 confident-wrong to wrong).

Turns judged: 6 (0 the code left unclear, 6 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 6 of 6 (2 to wrong, hedged; 4 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_candidates_still_in_running` run 1 turn 1: right / right
- `baseline` `hard_candidates_still_in_running` run 3 turn 1: right / wrong
- `baseline` `hard_revenue_per_session` run 3 turn 1: wrong / right
- `custom-metricflow` `hard_candidates_still_in_running` run 2 turn 1: right / right

## `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 123 of 123; model responses spent: custom-metricflow 421.

| | `custom-metricflow` |
|---|---|
| Accuracy | 55.3% |
| Confident-wrong | 0.8% |
| pass^3 | 53.7% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (22) accuracy | 81.8% |
| `trap` (5) accuracy | 100.0% |
| `uncovered` (19) accuracy | 24.6% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 6 (`custom-metricflow` 6 confident-wrong to wrong).

Turns judged: 3 (1 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 2 of 2 (1 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `hard_candidates_still_in_running` run 1 turn 1: wrong / confident-wrong

## `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 41 of 41 cases; runs finished: baseline 41 of 123, custom-metricflow 123 of 123, custom-hybrid 41 of 123; model responses spent: baseline 195, custom-metricflow 480, custom-hybrid 180.

| | `baseline` | `custom-metricflow` | `custom-hybrid` |
|---|---|---|---|
| Accuracy | 48.8% | 70.7% | 85.4% |
| Confident-wrong | 22.0% | 9.8% | 0.0% |
| pass^1 | 48.8% | 70.7% | 85.4% |
| `conversation` (8) accuracy | 12.5% | 62.5% | 62.5% |
| `covered` (22) accuracy | 50.0% | 81.8% | 86.4% |
| `trap` (5) accuracy | 60.0% | 100.0% | 100.0% |
| `uncovered` (19) accuracy | 47.4% | 57.9% | 84.2% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.220 [+0.024, +0.415]: a difference.
- Confident-wrong: -0.122 [-0.293, +0.049]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 2 (`baseline` 1 unclear to confident-wrong; `custom-hybrid` 1 wrong to declined).

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.
