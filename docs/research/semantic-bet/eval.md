# Every arm on the frozen set

Written 2026-11-03T14:16Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Arms are compared on one model, paired on the cases every arm reached.
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
Unclear turns (no number parses and no decline) await the blind judge and count as wrong here.

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

## `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 2 run(s) of 96 of 96 cases; runs finished: native-kc 288 of 288, native-shaped 207 of 288; model responses spent: native-kc 306, native-shaped 219.

| | `native-kc` | `native-shaped` |
|---|---|---|
| Accuracy | 64.1% | 61.5% |
| Confident-wrong | 4.2% | 5.7% |
| pass^2 | 62.5% | 59.4% |
| `conversation` (7) accuracy | 57.1% | 28.6% |
| `covered` (67) accuracy | 70.9% | 66.4% |
| `distractor` (3) accuracy | 83.3% | 83.3% |
| `planted` (4) accuracy | 100.0% | 100.0% |
| `trap` (11) accuracy | 59.1% | 54.5% |
| `uncovered` (29) accuracy | 48.3% | 50.0% |

The managed best (RULE.md § The rule, 1): `native-kc`, accuracy 64.1%.
No arm of ours (rung 3 or 4) ran on this model: nothing to compare it with.

Cases with an unclear turn: `bet_applicants_reaching_interview`, `bet_customers_september`, `bet_istanbul_warmer`, `bet_median_days_to_interview`, `bet_peak_page_view_hour`, `candidates_in_interview_as_of`
