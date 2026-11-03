# Every arm on the frozen set

Written 2026-11-03T21:59Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Arms are compared on one model, paired on the cases every arm reached.
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
Unclear turns (no number parses and no decline) await the blind judge and count as wrong here.
0 of `baseline`'s 48 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

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

Scored on all 3 runs of every case; runs finished: native-context-bare 288 of 288, native-context 288 of 288, native-governed 288 of 288, native-graph 288 of 288, native-kc-reach 288 of 288, native-kc 288 of 288, native-shaped 288 of 288; model responses spent: native-context-bare 306, native-context 306, native-governed 306, native-graph 306, native-kc-reach 306, native-kc 306, native-shaped 306.

| | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|
| Accuracy | 89.6% | 87.2% | 72.9% | 61.8% | 86.8% | 64.2% | 61.8% |
| Confident-wrong | 4.5% | 5.2% | 1.7% | 6.9% | 6.9% | 4.2% | 5.6% |
| pass^3 | 87.5% | 83.3% | 70.8% | 57.3% | 83.3% | 59.4% | 58.3% |
| `conversation` (7) accuracy | 71.4% | 66.7% | 71.4% | 42.9% | 33.3% | 52.4% | 33.3% |
| `covered` (67) accuracy | 97.0% | 94.0% | 91.0% | 68.7% | 87.6% | 71.1% | 66.7% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 88.9% | 77.8% |
| `planted` (4) accuracy | 100.0% | 100.0% | 66.7% | 83.3% | 100.0% | 100.0% | 100.0% |
| `trap` (11) accuracy | 100.0% | 100.0% | 100.0% | 63.6% | 87.9% | 63.6% | 51.5% |
| `uncovered` (29) accuracy | 72.4% | 71.3% | 31.0% | 46.0% | 85.1% | 48.3% | 50.6% |

The managed best (RULE.md § The rule, 1): `native-context-bare`, accuracy 89.6%.
No arm of ours (rung 3 or 4) ran on this model: nothing to compare it with.

Cases with an unclear turn: `bet_applicants_reaching_interview`, `bet_customers_over_three_orders`, `bet_customers_september`, `bet_istanbul_warmer`, `bet_median_days_to_hire`, `bet_median_days_to_interview`, `bet_median_session_minutes`, `bet_most_email_opens`, `bet_peak_page_view_hour`, `calls_about_returns`, `candidates_in_interview_as_of`, `customers_to_date`, `followup_day_before`, `leads_mtd`, `objection_rate`, `outreach_messages_sent`, `outreach_reply_rate`
