# Every arm on the bet's sets

Each set is scored on its own under [the rule](RULE.md), with its own comparison against the managed best: [the frozen set](#every-arm-on-the-frozen-set), then [the hard set](#every-arm-on-the-hard-set) (#356, #364).

## Every arm on the frozen set

Written 2026-11-03T22:27Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.

### `nvidia/nemotron-3.5-super-vl:free`

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

Turns judged: 2 (0 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 0 of 2 (0 to wrong, hedged; 0 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-lightdash` `cost_per_lead_search` run 1 turn 1: not judged yet
- `custom-lightdash` `median_order_value` run 1 turn 1: not judged yet

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 96 of 96 cases; runs finished: native-context 149 of 288, native-governed 161 of 288, native-graph 288 of 288, native-kc 288 of 288, native-shaped 288 of 288; model responses spent: native-context 159, native-governed 173, native-graph 306, native-kc 306, native-shaped 306.

| | `native-context` | `native-governed` | `native-graph` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|
| Accuracy | 87.5% | 72.9% | 61.5% | 64.6% | 61.5% |
| Confident-wrong | 6.2% | 1.0% | 7.3% | 4.2% | 5.2% |
| pass^1 | 87.5% | 72.9% | 61.5% | 64.6% | 61.5% |
| `conversation` (7) accuracy | 71.4% | 71.4% | 42.9% | 57.1% | 28.6% |
| `covered` (67) accuracy | 95.5% | 91.0% | 67.2% | 71.6% | 65.7% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 66.7% |
| `planted` (4) accuracy | 100.0% | 75.0% | 75.0% | 100.0% | 100.0% |
| `trap` (11) accuracy | 100.0% | 100.0% | 63.6% | 63.6% | 45.5% |
| `uncovered` (29) accuracy | 69.0% | 31.0% | 48.3% | 48.3% | 51.7% |

Turns judged: 20 (16 the code left unclear, 4 confident-wrong with a hedge outside the list); verdicts that stood: 20.
Confident-wrong turns the judge moved: 3 of 4 (3 to wrong, hedged; 0 to unclear).

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`, accuracy 87.5%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`, 47 of 96 cases: accuracy +0.011 [-0.053, +0.064], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 47 runs finished).
- `custom-lightdash` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`, 41 of 96 cases: accuracy -0.378 [-0.537, -0.232], confident-wrong +0.171 [+0.073, +0.293]: not worth building (decides; 41 runs finished).


## Every arm on the hard set

Written 2026-11-03T22:27Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl) and each live arm's `eval-hard-<arm>.jsonl` under [the rule](RULE.md): 43 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 31 of 43 cases; runs finished: native-context 85 of 129, native-governed 31 of 129, native-kc 129 of 129; model responses spent: native-context 94, native-governed 35, native-kc 141.

| | `native-context` | `native-governed` | `native-kc` |
|---|---|---|---|
| Accuracy | 87.1% | 77.4% | 61.3% |
| Confident-wrong | 0.0% | 0.0% | 16.1% |
| pass^1 | 87.1% | 77.4% | 61.3% |
| `conversation` (8) accuracy | 50.0% | 62.5% | 50.0% |
| `covered` (24) accuracy | 83.3% | 87.5% | 66.7% |
| `trap` (6) accuracy | 100.0% | 100.0% | 50.0% |
| `uncovered` (7) accuracy | 100.0% | 42.9% | 42.9% |

Turns still unclear after judging (counted as wrong):

- `native-kc` `hard_replies_within_12_hours` run 2 turn 1: not judged yet

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`, accuracy 87.1%.
No arm of ours (rung 3 or 4) is logged on any model: nothing to compare.
