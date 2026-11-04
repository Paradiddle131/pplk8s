# Every arm on the bet's sets

Each set is scored on its own under [the rule](RULE.md), with its own comparison against the managed best: [the frozen set](#every-arm-on-the-frozen-set), then [the hard set](#every-arm-on-the-hard-set) (#356, #364).

## Every arm on the frozen set

Written 2026-11-04T17:36Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
0 of `baseline`'s 336 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 41 of 96 cases; runs finished: baseline 48 of 288, custom-metricflow 110 of 288, custom-lightdash 41 of 288; model responses spent: baseline 221, custom-metricflow 409, custom-lightdash 77.

| | `baseline` | `custom-metricflow` | `custom-lightdash` |
|---|---|---|---|
| Accuracy | 63.4% | 95.1% | 58.5% |
| Confident-wrong | 14.6% | 0.0% | 9.8% |
| pass^1 | 63.4% | 95.1% | 58.5% |
| `covered` (39) accuracy | 64.1% | 100.0% | 61.5% |
| `distractor` (2) accuracy | 100.0% | 100.0% | 50.0% |
| `trap` (8) accuracy | 50.0% | 100.0% | 50.0% |
| `uncovered` (2) accuracy | 50.0% | 0.0% | 0.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.317 [+0.171, +0.463]: a difference.
- Confident-wrong: -0.146 [-0.268, -0.049]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 9 (4 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 9.
Confident-wrong turns the judge moved: 3 of 5 (3 to wrong, hedged; 0 to unclear).

### `claude-haiku-5-5`

Scored on partial: 1 run(s) of 34 of 96 cases; runs finished: baseline 288 of 288, custom-metricflow 288 of 288, custom-toolbox 56 of 288, native-mcp 38 of 288; model responses spent: baseline 1038, custom-metricflow 962, custom-toolbox 103, native-mcp 174.

| | `baseline` | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|
| Accuracy | 55.9% | 94.1% | 50.0% | 91.2% |
| Confident-wrong | 8.8% | 0.0% | 2.9% | 5.9% |
| pass^1 | 55.9% | 94.1% | 50.0% | 91.2% |
| `conversation` (3) accuracy | 66.7% | 100.0% | 33.3% | 66.7% |
| `covered` (32) accuracy | 56.2% | 100.0% | 53.1% | 90.6% |
| `distractor` (1) accuracy | 100.0% | 100.0% | 100.0% | 100.0% |
| `trap` (6) accuracy | 50.0% | 100.0% | 50.0% | 100.0% |
| `uncovered` (2) accuracy | 50.0% | 0.0% | 0.0% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.382 [+0.206, +0.559]: a difference.
- Confident-wrong: -0.088 [-0.206, +0.000]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 23 (11 the code left unclear, 12 confident-wrong with a hedge outside the list); verdicts that stood: 21.
Confident-wrong turns the judge moved: 11 of 12 (9 to wrong, hedged; 2 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `damaged_returns` run 3 turn 1: wrong / declined
- `baseline` `shipped_orders` run 3 turn 1: declined / wrong

### `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 288 of 288; model responses spent: custom-metricflow 931.

| | `custom-metricflow` |
|---|---|
| Accuracy | 74.7% |
| Confident-wrong | 1.4% |
| pass^3 | 71.9% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 99.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 18.4% |

Turns judged: 8 (8 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 8.

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 45 of 96 cases; runs finished: native-context-bare 288 of 288, native-context 288 of 288, native-governed 288 of 288, native-graph 288 of 288, native-kc-max 45 of 288, native-kc-reach 288 of 288, native-kc 288 of 288, native-shaped 288 of 288; model responses spent: native-context-bare 306, native-context 306, native-governed 306, native-graph 306, native-kc-max 45, native-kc-reach 306, native-kc 306, native-shaped 306.

| | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|
| Accuracy | 97.8% | 95.6% | 91.1% | 62.2% | 91.1% | 88.9% | 64.4% | 64.4% |
| Confident-wrong | 0.0% | 0.0% | 0.0% | 8.9% | 6.7% | 8.9% | 6.7% | 6.7% |
| pass^1 | 97.8% | 95.6% | 91.1% | 62.2% | 91.1% | 88.9% | 64.4% | 64.4% |
| `covered` (43) accuracy | 100.0% | 97.7% | 93.0% | 65.1% | 93.0% | 93.0% | 67.4% | 65.1% |
| `distractor` (2) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 50.0% |
| `trap` (8) accuracy | 100.0% | 100.0% | 100.0% | 50.0% | 87.5% | 87.5% | 50.0% | 37.5% |
| `uncovered` (2) accuracy | 50.0% | 50.0% | 50.0% | 0.0% | 50.0% | 0.0% | 0.0% | 50.0% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 6 (`native-governed` 1 confident-wrong to wrong; `native-governed` 2 unclear to declined; `native-shaped` 1 confident-wrong to wrong; `native-shaped` 2 unclear to declined).

Turns judged: 24 (19 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 24.
Confident-wrong turns the judge moved: 1 of 5 (1 to wrong, hedged; 0 to unclear).

### `google-data-agent (LATEST_GA_MODEL)`

Scored on partial: 1 run(s) of 1 of 96 cases; runs finished: native-context-bare 1 of 288; model responses spent: native-context-bare 1.

| | `native-context-bare` |
|---|---|
| Accuracy | 100.0% |
| Confident-wrong | 0.0% |
| pass^1 | 100.0% |
| `covered` (1) accuracy | 100.0% |
| `trap` (1) accuracy | 100.0% |

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on partial: 1 run(s) of 1 of 96 cases; runs finished: native-context-bare 1 of 288; model responses spent: native-context-bare 1.

| | `native-context-bare` |
|---|---|
| Accuracy | 100.0% |
| Confident-wrong | 0.0% |
| pass^1 | 100.0% |
| `covered` (1) accuracy | 100.0% |
| `trap` (1) accuracy | 100.0% |

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on partial: 1 run(s) of 1 of 96 cases; runs finished: native-context-bare 1 of 288; model responses spent: native-context-bare 1.

| | `native-context-bare` |
|---|---|
| Accuracy | 100.0% |
| Confident-wrong | 0.0% |
| pass^1 | 100.0% |
| `covered` (1) accuracy | 100.0% |
| `trap` (1) accuracy | 100.0% |

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)`, accuracy 100.0%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)`, 1 of 96 cases: accuracy +0.000 [+0.000, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 110 runs finished).
- `custom-lightdash` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)`, 1 of 96 cases: accuracy +0.000 [+0.000, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 41 runs finished).
- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)`, 1 of 96 cases: accuracy +0.000 [+0.000, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 288 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)`, 1 of 96 cases: accuracy +0.000 [+0.000, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 56 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)`, 1 of 96 cases: accuracy +0.000 [+0.000, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 38 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)`, 1 of 96 cases: accuracy +0.000 [+0.000, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 288 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.

## Every arm on the hard set

Written 2026-11-04T17:36Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl) and each live arm's `eval-hard-<arm>.jsonl` under [the rule](RULE.md): 43 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
129 of `baseline`'s 129 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `claude-haiku-5-5`

Scored on all 3 runs of every case; runs finished: baseline 129 of 129, custom-metricflow 129 of 129; model responses spent: baseline 510, custom-metricflow 437.

| | `baseline` | `custom-metricflow` |
|---|---|---|
| Accuracy | 56.6% | 73.6% |
| Confident-wrong | 7.8% | 9.3% |
| pass^3 | 51.2% | 67.4% |
| `conversation` (8) accuracy | 37.5% | 62.5% |
| `covered` (24) accuracy | 66.7% | 87.5% |
| `trap` (6) accuracy | 55.6% | 100.0% |
| `uncovered` (19) accuracy | 43.9% | 56.1% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.171 [+0.031, +0.318]: a difference.
- Confident-wrong: +0.016 [-0.078, +0.116]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 6 (0 the code left unclear, 6 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 6 of 6 (2 to wrong, hedged; 4 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_candidates_still_in_running` run 1 turn 1: right / right
- `baseline` `hard_candidates_still_in_running` run 3 turn 1: right / wrong
- `baseline` `hard_revenue_per_session` run 3 turn 1: wrong / right
- `custom-metricflow` `hard_candidates_still_in_running` run 2 turn 1: right / right

### `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 129 of 129; model responses spent: custom-metricflow 445.

| | `custom-metricflow` |
|---|---|
| Accuracy | 57.4% |
| Confident-wrong | 5.4% |
| pass^3 | 55.8% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (24) accuracy | 83.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 24.6% |

Turns judged: 3 (1 the code left unclear, 2 confident-wrong with a hedge outside the list); verdicts that stood: 2.
Confident-wrong turns the judge moved: 2 of 2 (1 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `hard_candidates_still_in_running` run 1 turn 1: wrong / confident-wrong

### `nvidia/nemotron-3.5-super-vl:free`

Scored on all 3 runs of every case; runs finished: custom-metricflow 129 of 129; model responses spent: custom-metricflow 502.

| | `custom-metricflow` |
|---|---|
| Accuracy | 73.6% |
| Confident-wrong | 7.0% |
| pass^3 | 62.8% |
| `conversation` (8) accuracy | 58.3% |
| `covered` (24) accuracy | 83.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 61.4% |

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on all 3 runs of every case; runs finished: native-context-bare 129 of 129, native-context 129 of 129, native-governed 129 of 129, native-graph 129 of 129, native-kc-reach 129 of 129, native-kc 129 of 129, native-shaped 129 of 129; model responses spent: native-context-bare 141, native-context 142, native-governed 141, native-graph 141, native-kc-reach 141, native-kc 141, native-shaped 141.

| | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|
| Accuracy | 93.0% | 92.2% | 69.8% | 55.0% | 86.8% | 63.6% | 60.5% |
| Confident-wrong | 0.0% | 0.0% | 1.6% | 17.8% | 6.2% | 13.2% | 13.2% |
| pass^3 | 90.7% | 90.7% | 62.8% | 48.8% | 81.4% | 55.8% | 55.8% |
| `conversation` (8) accuracy | 62.5% | 58.3% | 66.7% | 45.8% | 62.5% | 54.2% | 37.5% |
| `covered` (24) accuracy | 87.5% | 86.1% | 86.1% | 61.1% | 83.3% | 66.7% | 54.2% |
| `trap` (6) accuracy | 100.0% | 100.0% | 100.0% | 38.9% | 83.3% | 50.0% | 38.9% |
| `uncovered` (19) accuracy | 100.0% | 100.0% | 49.1% | 47.4% | 91.2% | 59.6% | 68.4% |

Turns judged: 12 (7 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 12.
Confident-wrong turns the judge moved: 1 of 5 (1 to wrong, hedged; 0 to unclear).

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, accuracy 93.0%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 43 of 43 cases: accuracy -0.194 [-0.318, -0.078], confident-wrong +0.093 [+0.023, +0.178]: not worth building (the check; 129 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 43 of 43 cases: accuracy -0.357 [-0.504, -0.217], confident-wrong +0.054 [+0.000, +0.124]: not worth building (the check; 129 runs finished).
- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 43 of 43 cases: accuracy -0.194 [-0.310, -0.085], confident-wrong +0.070 [+0.023, +0.124]: not worth building (decides; 129 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.

### The rule on both sets

RULE.md § Changes since freezing (#356): each set goes through the rule on its own; an arm of ours is worth building only if step 2 holds on both sets, and where they disagree the cheaper rung wins, as a tie does.
- The managed best on the frozen set: `native-context-bare` on `google-data-agent (LATEST_GA_MODEL)`, 100.0%.
- The managed best on the hard set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED)`, 93.0%.
- `custom-metricflow` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-lightdash` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-metricflow` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-toolbox` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `native-mcp` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-metricflow` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
Step 3 (the cheapest arm with no accuracy difference from the best on both sets) is read in the report, not computed here.
