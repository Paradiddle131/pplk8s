# Every arm on the frozen set

Written 2026-11-03T13:14Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
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

Scored on all 3 runs of every case; runs finished: native-kc 288 of 288; model responses spent: native-kc 306.

| | `native-kc` |
|---|---|
| Accuracy | 64.2% |
| Confident-wrong | 4.2% |
| pass^3 | 59.4% |
| `conversation` (7) accuracy | 52.4% |
| `covered` (67) accuracy | 71.1% |
| `distractor` (3) accuracy | 88.9% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 63.6% |
| `uncovered` (29) accuracy | 48.3% |

The managed best (RULE.md § The rule, 1): `native-kc`, accuracy 64.2%.
No arm of ours (rung 3 or 4) ran on this model: nothing to compare it with.
