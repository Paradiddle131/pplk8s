# Every arm on the frozen set

Written 2026-11-03T20:29Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Arms are compared on one model, paired on the cases every arm reached.
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
Unclear turns (no number parses and no decline) await the blind judge and count as wrong here.

## `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 41 of 96 cases; runs finished: baseline 48 of 288, custom-metricflow 47 of 288, custom-lightdash 41 of 288; model responses spent: baseline 221, custom-metricflow 179, custom-lightdash 77.

| | `baseline` | `custom-metricflow` | `custom-lightdash` |
|---|---|---|---|
| Accuracy | 63.4% | 95.1% | 58.5% |
| Confident-wrong | 14.6% | 0.0% | 17.1% |
| pass^1 | 63.4% | 95.1% | 58.5% |
| `covered` (39) accuracy | 64.1% | 100.0% | 61.5% |
| `distractor` (2) accuracy | 100.0% | 100.0% | 50.0% |
| `trap` (8) accuracy | 50.0% | 100.0% | 50.0% |
| `uncovered` (2) accuracy | 50.0% | 0.0% | 0.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.317 [+0.171, +0.463]: a difference.
- Confident-wrong: -0.146 [-0.268, -0.049]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Cases with an unclear turn: `cost_per_lead_search`, `median_order_value`

## `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 96 of 96 cases; runs finished: native-context 149 of 288, native-governed 161 of 288, native-graph 288 of 288, native-kc 288 of 288, native-shaped 288 of 288; model responses spent: native-context 159, native-governed 173, native-graph 306, native-kc 306, native-shaped 306.

| | `native-context` | `native-governed` | `native-graph` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|
| Accuracy | 87.5% | 72.9% | 61.5% | 64.6% | 61.5% |
| Confident-wrong | 6.2% | 3.1% | 7.3% | 4.2% | 5.2% |
| pass^1 | 87.5% | 72.9% | 61.5% | 64.6% | 61.5% |
| `conversation` (7) accuracy | 71.4% | 71.4% | 42.9% | 57.1% | 28.6% |
| `covered` (67) accuracy | 95.5% | 91.0% | 67.2% | 71.6% | 65.7% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 66.7% |
| `planted` (4) accuracy | 100.0% | 75.0% | 75.0% | 100.0% | 100.0% |
| `trap` (11) accuracy | 100.0% | 100.0% | 63.6% | 63.6% | 45.5% |
| `uncovered` (29) accuracy | 69.0% | 31.0% | 48.3% | 48.3% | 51.7% |

The managed best (RULE.md § The rule, 1): `native-context`, accuracy 87.5%.
No arm of ours (rung 3 or 4) ran on this model: nothing to compare it with.

Cases with an unclear turn: `bet_customers_september`, `bet_median_days_to_interview`, `bet_peak_page_view_hour`
