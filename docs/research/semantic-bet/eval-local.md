# The bet's local arms on the frozen set

Written 2026-11-09T00:33Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl), the log of every run, under [the rule](RULE.md): 76 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
34 of `baseline`'s 296 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

## `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 76 of 76 cases; runs finished: baseline 76 of 228, custom-metricflow 89 of 228, custom-hybrid 76 of 228, custom-metricflow-compute 76 of 228; model responses spent: baseline 347, custom-metricflow 343, custom-hybrid 311, custom-metricflow-compute 277.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-metricflow-compute` |
|---|---|---|---|---|
| Accuracy | 59.2% | 89.5% | 89.5% | 89.5% |
| Confident-wrong | 9.2% | 0.0% | 0.0% | 0.0% |
| pass^1 | 59.2% | 89.5% | 89.5% | 89.5% |
| `conversation` (7) accuracy | 42.9% | 100.0% | 100.0% | 100.0% |
| `covered` (61) accuracy | 68.9% | 100.0% | 100.0% | 100.0% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% | 100.0% |
| `trap` (10) accuracy | 60.0% | 100.0% | 100.0% | 100.0% |
| `uncovered` (15) accuracy | 20.0% | 46.7% | 46.7% | 46.7% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.303 [+0.197, +0.408]: a difference.
- Confident-wrong: -0.092 [-0.158, -0.039]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 2 (`baseline` 1 unclear to confident-wrong; `custom-metricflow` 1 unclear to declined).

Turns judged: 2 (0 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 0 of 2 (0 to wrong, hedged; 0 to unclear).

## `claude-haiku-5-5`

Scored on partial: 1 run(s) of 72 of 76 cases; runs finished: baseline 220 of 228, custom-metricflow 225 of 228, custom-hybrid 225 of 228; model responses spent: baseline 785, custom-metricflow 753, custom-hybrid 805.

| | `baseline` | `custom-metricflow` | `custom-hybrid` |
|---|---|---|---|
| Accuracy | 62.5% | 88.9% | 87.5% |
| Confident-wrong | 6.9% | 1.4% | 4.2% |
| pass^1 | 62.5% | 88.9% | 87.5% |
| `conversation` (6) accuracy | 66.7% | 100.0% | 100.0% |
| `covered` (58) accuracy | 72.4% | 98.3% | 94.8% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% |
| `trap` (9) accuracy | 66.7% | 100.0% | 100.0% |
| `uncovered` (14) accuracy | 21.4% | 50.0% | 57.1% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.264 [+0.153, +0.375]: a difference.
- Confident-wrong: -0.056 [-0.125, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 1 (`custom-metricflow` 1 confident-wrong to wrong).

Turns judged: 38 (23 the code left unclear, 15 confident-wrong with a hedge outside the list); verdicts that stood: 33.
Confident-wrong turns the judge moved: 14 of 15 (9 to wrong, hedged; 5 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `damaged_returns` run 3 turn 1: wrong / declined
- `baseline` `shipped_orders` run 3 turn 1: declined / wrong
- `custom-hybrid` `calls_about_returns` run 3 turn 1: right / right
- `custom-hybrid` `signups_september` run 2 turn 1: right / right
- `custom-hybrid` `signups_september` run 3 turn 1: right / right

## `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 228 of 228; model responses spent: custom-metricflow 743.

| | `custom-metricflow` |
|---|---|
| Accuracy | 82.0% |
| Confident-wrong | 0.9% |
| pass^3 | 80.3% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 98.9% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (15) accuracy | 13.3% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 2 (`custom-metricflow` 1 confident-wrong to wrong; `custom-metricflow` 1 unclear to declined).

Turns judged: 4 (4 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 4.

## `claude-opus-5-5`

Scored on partial: 1 run(s) of 74 of 76 cases; runs finished: custom-metricflow 226 of 228; model responses spent: custom-metricflow 743.

| | `custom-metricflow` |
|---|---|
| Accuracy | 82.4% |
| Confident-wrong | 1.4% |
| pass^1 | 82.4% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (61) accuracy | 100.0% |
| `distractor` (1) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (10) accuracy | 100.0% |
| `uncovered` (13) accuracy | 0.0% |

Turns judged: 3 (2 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 3.
Confident-wrong turns the judge moved: 1 of 1 (1 to wrong, hedged; 0 to unclear).

## Errors

- No answer: the model call failed (litellm.APIError: APIError: OpenrouterException - Response payload is not completed: <TransferEncodingError: 400, message='Not enough data to satisfy transfer length header.'> LiteLLM Retried: 2 times).
