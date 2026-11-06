# Every arm on the bet's sets

Each set is scored on its own under [the rule](RULE.md), with its own comparison against the managed best: [the frozen set](#every-arm-on-the-frozen-set), then [the hard set](#every-arm-on-the-hard-set) (#356, #364).

## Every arm on the frozen set

Written 2026-11-06T00:37Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-local.jsonl`](eval-local.jsonl) and each live arm's `eval-<arm>.jsonl` under [the rule](RULE.md): 96 cases of `services/semantic-agent/evals/semantic_bet.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
0 of `baseline`'s 336 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 37 of 96 cases; runs finished: baseline 48 of 288, custom-metricflow 110 of 288, custom-hybrid 96 of 288, custom-lightdash 41 of 288, native-mcp 37 of 288; model responses spent: baseline 221, custom-metricflow 409, custom-hybrid 409, custom-lightdash 77, native-mcp 225.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-lightdash` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 59.5% | 94.6% | 97.3% | 56.8% | 94.6% |
| Confident-wrong | 16.2% | 0.0% | 0.0% | 10.8% | 5.4% |
| pass^1 | 59.5% | 94.6% | 97.3% | 56.8% | 94.6% |
| `covered` (35) accuracy | 60.0% | 100.0% | 100.0% | 60.0% | 94.3% |
| `distractor` (2) accuracy | 100.0% | 100.0% | 100.0% | 50.0% | 50.0% |
| `trap` (8) accuracy | 50.0% | 100.0% | 100.0% | 50.0% | 87.5% |
| `uncovered` (2) accuracy | 50.0% | 0.0% | 50.0% | 0.0% | 100.0% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.351 [+0.189, +0.514]: a difference.
- Confident-wrong: -0.162 [-0.297, -0.054]: a difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 10 (4 the code left unclear, 6 confident-wrong with a hedge outside the list); verdicts that stood: 10.
Confident-wrong turns the judge moved: 3 of 6 (3 to wrong, hedged; 0 to unclear).

### `claude-haiku-5-5`

Scored on all 3 runs of every case; runs finished: baseline 288 of 288, custom-metricflow 288 of 288, custom-hybrid 288 of 288, custom-toolbox 288 of 288, native-mcp 288 of 288; model responses spent: baseline 1038, custom-metricflow 962, custom-hybrid 1052, custom-toolbox 485, native-mcp 1383.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 61.1% | 81.2% | 80.9% | 43.1% | 90.3% |
| Confident-wrong | 6.6% | 2.4% | 3.1% | 3.1% | 3.1% |
| pass^3 | 56.2% | 78.1% | 77.1% | 40.6% | 82.3% |
| `conversation` (7) accuracy | 57.1% | 95.2% | 100.0% | 42.9% | 61.9% |
| `covered` (67) accuracy | 71.6% | 97.5% | 94.5% | 52.7% | 90.5% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 88.9% |
| `planted` (4) accuracy | 100.0% | 100.0% | 100.0% | 75.0% | 83.3% |
| `trap` (11) accuracy | 66.7% | 97.0% | 93.9% | 54.5% | 97.0% |
| `uncovered` (29) accuracy | 36.8% | 43.7% | 49.4% | 20.7% | 89.7% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.201 [+0.108, +0.295]: a difference.
- Confident-wrong: -0.042 [-0.090, +0.003]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 46 (29 the code left unclear, 17 confident-wrong with a hedge outside the list); verdicts that stood: 39.
Confident-wrong turns the judge moved: 16 of 17 (9 to wrong, hedged; 7 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `damaged_returns` run 3 turn 1: wrong / declined
- `baseline` `shipped_orders` run 3 turn 1: declined / wrong
- `custom-hybrid` `calls_about_returns` run 3 turn 1: right / right
- `custom-hybrid` `signups_september` run 2 turn 1: right / right
- `custom-hybrid` `signups_september` run 3 turn 1: right / right
- `native-mcp` `bet_applicants_reaching_interview` run 2 turn 1: right / right
- `native-mcp` `signups_september` run 3 turn 1: right / right

### `claude-sonnet-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 288 of 288, custom-toolbox 288 of 288, native-mcp 288 of 288; model responses spent: custom-metricflow 931, custom-toolbox 472, native-mcp 1290.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 74.7% | 41.7% | 95.8% |
| Confident-wrong | 1.4% | 2.4% | 0.7% |
| pass^3 | 71.9% | 40.6% | 93.8% |
| `conversation` (7) accuracy | 100.0% | 42.9% | 71.4% |
| `covered` (67) accuracy | 99.0% | 50.7% | 96.0% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% |
| `planted` (4) accuracy | 100.0% | 50.0% | 83.3% |
| `trap` (11) accuracy | 100.0% | 54.5% | 100.0% |
| `uncovered` (29) accuracy | 18.4% | 20.7% | 95.4% |

Turns judged: 16 (12 the code left unclear, 4 confident-wrong with a hedge outside the list); verdicts that stood: 16.
Confident-wrong turns the judge moved: 2 of 4 (2 to wrong, hedged; 0 to unclear).

### `claude-opus-5-5`

Scored on all 3 runs of every case; runs finished: custom-metricflow 288 of 288; model responses spent: custom-metricflow 932.

| | `custom-metricflow` |
|---|---|
| Accuracy | 74.7% |
| Confident-wrong | 1.7% |
| pass^3 | 74.0% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 100.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 16.1% |

Turns judged: 6 (5 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 6.
Confident-wrong turns the judge moved: 1 of 1 (1 to wrong, hedged; 0 to unclear).

### `claude-code (haiku)`

Scored on partial: 1 run(s) of 96 of 96 cases; runs finished: cc-metricflow 96 of 288; model responses spent: cc-metricflow 102.

| | `cc-metricflow` |
|---|---|
| Accuracy | 66.7% |
| Confident-wrong | 5.2% |
| pass^1 | 66.7% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 92.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 75.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 6.9% |

Turns judged: 6 (6 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 6.

### `claude-code (sonnet)`

Scored on partial: 1 run(s) of 96 of 96 cases; runs finished: cc-metricflow 96 of 288; model responses spent: cc-metricflow 102.

| | `cc-metricflow` |
|---|---|
| Accuracy | 70.8% |
| Confident-wrong | 1.0% |
| pass^1 | 70.8% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 100.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 3.4% |

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

### `claude-code (opus)`

Scored on partial: 1 run(s) of 96 of 96 cases; runs finished: cc-metricflow 96 of 288; model responses spent: cc-metricflow 102.

| | `cc-metricflow` |
|---|---|
| Accuracy | 70.8% |
| Confident-wrong | 4.2% |
| pass^1 | 70.8% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 98.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 6.9% |

Turns judged: 4 (4 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 4.

### `claude-code (fresh-haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 288 of 288; model responses spent: cc-metricflow 306.

| | `cc-metricflow` |
|---|---|
| Accuracy | 72.6% |
| Confident-wrong | 4.5% |
| pass^3 | 67.7% |
| `conversation` (7) accuracy | 95.2% |
| `covered` (67) accuracy | 96.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 17.2% |

Turns judged: 2 (2 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 2.

### `claude-code (fresh-sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 288 of 288; model responses spent: cc-metricflow 306.

| | `cc-metricflow` |
|---|---|
| Accuracy | 72.9% |
| Confident-wrong | 2.1% |
| pass^3 | 69.8% |
| `conversation` (7) accuracy | 95.2% |
| `covered` (67) accuracy | 97.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 75.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 16.1% |

Turns judged: 3 (3 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 3.

### `claude-code (fresh-opus)`

Scored on partial: 1 run(s) of 50 of 96 cases; runs finished: cc-metricflow 50 of 288; model responses spent: cc-metricflow 54.

| | `cc-metricflow` |
|---|---|
| Accuracy | 74.0% |
| Confident-wrong | 0.0% |
| pass^1 | 74.0% |
| `conversation` (4) accuracy | 100.0% |
| `covered` (35) accuracy | 100.0% |
| `distractor` (2) accuracy | 100.0% |
| `planted` (2) accuracy | 100.0% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (15) accuracy | 13.3% |

### `claude-code (subject-haiku)`

Scored on partial: 1 run(s) of 96 of 96 cases; runs finished: cc-metricflow 96 of 288; model responses spent: cc-metricflow 102.

| | `cc-metricflow` |
|---|---|
| Accuracy | 69.8% |
| Confident-wrong | 4.2% |
| pass^1 | 69.8% |
| `conversation` (7) accuracy | 100.0% |
| `covered` (67) accuracy | 95.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 10.3% |

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 95 of 96 cases; runs finished: native-bare 287 of 288, native-context-bare 288 of 288, native-context 288 of 288, native-governed 288 of 288, native-graph 288 of 288, native-kc-max 288 of 288, native-kc-reach 288 of 288, native-kc 288 of 288, native-shaped 288 of 288; model responses spent: native-bare 305, native-context-bare 306, native-context 306, native-governed 306, native-graph 306, native-kc-max 306, native-kc-reach 306, native-kc 306, native-shaped 306.

| | `native-bare` | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 80.0% | 89.5% | 87.4% | 72.6% | 61.1% | 90.5% | 86.3% | 64.2% | 61.1% |
| Confident-wrong | 15.8% | 4.2% | 6.3% | 1.1% | 7.4% | 5.3% | 7.4% | 4.2% | 5.3% |
| pass^1 | 80.0% | 89.5% | 87.4% | 72.6% | 61.1% | 90.5% | 86.3% | 64.2% | 61.1% |
| `conversation` (7) accuracy | 28.6% | 71.4% | 71.4% | 71.4% | 42.9% | 42.9% | 28.6% | 57.1% | 28.6% |
| `covered` (66) accuracy | 75.8% | 97.0% | 95.5% | 90.9% | 66.7% | 89.4% | 86.4% | 71.2% | 65.2% |
| `distractor` (3) accuracy | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 66.7% |
| `planted` (4) accuracy | 75.0% | 100.0% | 100.0% | 75.0% | 75.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| `trap` (10) accuracy | 60.0% | 100.0% | 100.0% | 100.0% | 60.0% | 90.0% | 90.0% | 60.0% | 40.0% |
| `uncovered` (29) accuracy | 89.7% | 72.4% | 69.0% | 31.0% | 48.3% | 93.1% | 86.2% | 48.3% | 51.7% |

Turns the current wordings score otherwise than their log (RULE.md § Changes since freezing, applied on read): 6 (`native-governed` 1 confident-wrong to wrong; `native-governed` 2 unclear to declined; `native-shaped` 1 confident-wrong to wrong; `native-shaped` 2 unclear to declined).

Turns judged: 24 (19 the code left unclear, 5 confident-wrong with a hedge outside the list); verdicts that stood: 24.
Confident-wrong turns the judge moved: 1 of 5 (1 to wrong, hedged; 0 to unclear).

### `google-data-agent (LATEST_GA_MODEL)`

Scored on all 3 runs of every case; runs finished: native-context-bare 288 of 288; model responses spent: native-context-bare 306.

| | `native-context-bare` |
|---|---|
| Accuracy | 90.3% |
| Confident-wrong | 5.2% |
| pass^3 | 88.5% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (67) accuracy | 97.0% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 74.7% |

Turns judged: 1 (0 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 1.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on all 3 runs of every case; runs finished: native-context-bare 288 of 288; model responses spent: native-context-bare 306.

| | `native-context-bare` |
|---|---|
| Accuracy | 94.1% |
| Confident-wrong | 1.0% |
| pass^3 | 92.7% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (67) accuracy | 96.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 100.0% |
| `uncovered` (29) accuracy | 88.5% |

Turns judged: 2 (1 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 1.
Confident-wrong turns the judge moved: 1 of 1 (0 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `native-context-bare` `bet_p90_order` run 2 turn 1: right / right

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on all 3 runs of every case; runs finished: native-context-bare 288 of 288; model responses spent: native-context-bare 306.

| | `native-context-bare` |
|---|---|
| Accuracy | 90.3% |
| Confident-wrong | 4.5% |
| pass^3 | 87.5% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (67) accuracy | 96.5% |
| `distractor` (3) accuracy | 88.9% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 97.0% |
| `uncovered` (29) accuracy | 75.9% |

Turns judged: 1 (0 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 1.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, accuracy 94.1%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.128 [-0.208, -0.049], confident-wrong -0.010 [-0.031, +0.000]: not worth building (decides; 110 runs finished).
- `custom-hybrid` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.087 [-0.170, -0.007], confident-wrong +0.000 [-0.031, +0.031]: not worth building (decides; 96 runs finished).
- `custom-lightdash` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 41 of 96 cases: accuracy -0.382 [-0.537, -0.236], confident-wrong +0.098 [+0.024, +0.195]: not worth building (decides; 41 runs finished).
- `native-mcp` (rung 3) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 37 of 96 cases: accuracy -0.018 [-0.108, +0.072], confident-wrong +0.054 [+0.000, +0.135]: not worth building (decides; 37 runs finished).
- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.128 [-0.208, -0.052], confident-wrong +0.014 [-0.017, +0.042]: not worth building (the check; 288 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.132 [-0.219, -0.045], confident-wrong +0.021 [-0.010, +0.052]: not worth building (the check; 288 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.510 [-0.608, -0.410], confident-wrong +0.021 [-0.014, +0.059]: not worth building (the check; 288 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.038 [-0.094, +0.017], confident-wrong +0.021 [-0.010, +0.049]: not worth building (the check; 288 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.194 [-0.285, -0.108], confident-wrong +0.003 [-0.024, +0.028]: not worth building (the check; 288 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.524 [-0.625, -0.424], confident-wrong +0.014 [-0.021, +0.049]: not worth building (the check; 288 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy +0.017 [-0.021, +0.062], confident-wrong -0.003 [-0.028, +0.014]: not worth building (the check; 288 runs finished).
- `custom-metricflow` (rung 4) on `claude-opus-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.194 [-0.288, -0.108], confident-wrong +0.007 [-0.024, +0.038]: not worth building (the check; 288 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.274 [-0.375, -0.177], confident-wrong +0.042 [+0.000, +0.094]: not worth building (the check; 96 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.233 [-0.330, -0.139], confident-wrong +0.000 [-0.031, +0.031]: not worth building (the check; 96 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.233 [-0.330, -0.139], confident-wrong +0.031 [-0.010, +0.073]: not worth building (the check; 96 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.215 [-0.306, -0.132], confident-wrong +0.035 [-0.003, +0.073]: not worth building (the check; 288 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.212 [-0.302, -0.125], confident-wrong +0.010 [-0.017, +0.038]: not worth building (the check; 288 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 50 of 96 cases: accuracy -0.187 [-0.307, -0.067], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 50 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (subject-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 96 of 96 cases: accuracy -0.243 [-0.340, -0.149], confident-wrong +0.031 [-0.010, +0.083]: not worth building (the check; 96 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-hybrid`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow`: the same verdict on every model, so the gap is not the model's.

### Errors

- No answer: the model call failed (litellm.APIError: APIError: OpenrouterException - Response payload is not completed: <TransferEncodingError: 400, message='Not enough data to satisfy transfer length header.'> LiteLLM Retried: 2 times).

## Every arm on the hard set

Written 2026-11-06T00:37Z by `make agent-eval ARM=bet` (`semantic_agent/bet_eval.py`) from [`eval-hard-local.jsonl`](eval-hard-local.jsonl) and each live arm's `eval-hard-<arm>.jsonl` under [the rule](RULE.md): 43 cases of `services/semantic-agent/evals/semantic_bet_hard.yaml`, k = 3 runs each, each run in a fresh session, on `dbt/dev/fixture.sql` and `fixture_weeks.sql` in the Compose warehouse.
Within a model, arms stand side by side on the cases every arm reached; the rule's comparison pairs arms by case across models, each arm's model named (RULE.md § The rule, 2).
`custom-metricflow` is the semantic agent on its MetricFlow tools; it cannot read the `legacy` schema (RULE.md § The arms). `baseline` is the text-to-SQL baseline that reads the generated docs.
A turn the code cannot decide (no number parses and no decline) goes to the blind judge, `nvidia/nemotron-3-ultra-550b-a55b:free` asked 2 times ([`judge.jsonl`](judge.jsonl), RULE.md § Scoring a run): equal verdicts stand; a turn still unclear counts as wrong and is listed under its model.
129 of `baseline`'s 129 logged runs had the `legacy` tables in reach (logged with `legacy`, from #357 on); the others did not.

### `claude-haiku-5-5`

Scored on all 3 runs of every case; runs finished: baseline 129 of 129, custom-metricflow 129 of 129, custom-hybrid 129 of 129, custom-toolbox 129 of 129, native-mcp 129 of 129; model responses spent: baseline 510, custom-metricflow 437, custom-hybrid 480, custom-toolbox 259, native-mcp 662.

| | `baseline` | `custom-metricflow` | `custom-hybrid` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|---|---|
| Accuracy | 56.6% | 73.6% | 81.4% | 45.0% | 81.4% |
| Confident-wrong | 7.8% | 9.3% | 3.1% | 7.0% | 6.2% |
| pass^3 | 51.2% | 67.4% | 79.1% | 44.2% | 72.1% |
| `conversation` (8) accuracy | 37.5% | 62.5% | 62.5% | 25.0% | 45.8% |
| `covered` (24) accuracy | 66.7% | 87.5% | 87.5% | 55.6% | 76.4% |
| `trap` (6) accuracy | 55.6% | 100.0% | 100.0% | 55.6% | 94.4% |
| `uncovered` (19) accuracy | 43.9% | 56.1% | 73.7% | 31.6% | 87.7% |

Paired by case, `custom-metricflow` minus `baseline`, percentile bootstrap 95% (10,000 resamples, seed 325):

- Accuracy: +0.171 [+0.031, +0.318]: a difference.
- Confident-wrong: +0.016 [-0.078, +0.116]: no difference.

Both local arms are on rung 3 or 4 and none is the managed best, so this pair is descriptive (RULE.md § The rule, 5) until the native arms are scored.

Turns judged: 8 (1 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 3.
Confident-wrong turns the judge moved: 7 of 7 (2 to wrong, hedged; 5 to unclear).

Turns still unclear after judging (counted as wrong):

- `baseline` `hard_candidates_still_in_running` run 1 turn 1: right / right
- `baseline` `hard_candidates_still_in_running` run 3 turn 1: right / wrong
- `baseline` `hard_revenue_per_session` run 3 turn 1: wrong / right
- `custom-metricflow` `hard_candidates_still_in_running` run 2 turn 1: right / right
- `native-mcp` `hard_replies_within_12_hours` run 2 turn 1: right / right

### `claude-sonnet-5-5`

Scored on partial: 2 run(s) of 43 of 43 cases; runs finished: custom-metricflow 129 of 129, custom-toolbox 129 of 129, native-mcp 87 of 129; model responses spent: custom-metricflow 445, custom-toolbox 257, native-mcp 403.

| | `custom-metricflow` | `custom-toolbox` | `native-mcp` |
|---|---|---|---|
| Accuracy | 57.0% | 47.7% | 89.5% |
| Confident-wrong | 5.8% | 5.8% | 0.0% |
| pass^2 | 55.8% | 46.5% | 88.4% |
| `conversation` (8) accuracy | 62.5% | 37.5% | 50.0% |
| `covered` (24) accuracy | 83.3% | 60.4% | 81.2% |
| `trap` (6) accuracy | 100.0% | 66.7% | 100.0% |
| `uncovered` (19) accuracy | 23.7% | 31.6% | 100.0% |

Turns judged: 10 (2 the code left unclear, 8 confident-wrong with a hedge outside the list); verdicts that stood: 9.
Confident-wrong turns the judge moved: 5 of 8 (4 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `custom-metricflow` `hard_candidates_still_in_running` run 1 turn 1: wrong / confident-wrong

### `nvidia/nemotron-3.5-super-vl:free`

Scored on partial: 1 run(s) of 43 of 43 cases; runs finished: custom-metricflow 129 of 129, custom-hybrid 43 of 129; model responses spent: custom-metricflow 502, custom-hybrid 189.

| | `custom-metricflow` | `custom-hybrid` |
|---|---|---|
| Accuracy | 72.1% | 86.0% |
| Confident-wrong | 9.3% | 0.0% |
| pass^1 | 72.1% | 86.0% |
| `conversation` (8) accuracy | 62.5% | 62.5% |
| `covered` (24) accuracy | 83.3% | 87.5% |
| `trap` (6) accuracy | 100.0% | 100.0% |
| `uncovered` (19) accuracy | 57.9% | 84.2% |

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

### `claude-code (haiku)`

Scored on partial: 1 run(s) of 43 of 43 cases; runs finished: cc-metricflow 43 of 129; model responses spent: cc-metricflow 47.

| | `cc-metricflow` |
|---|---|
| Accuracy | 44.2% |
| Confident-wrong | 18.6% |
| pass^1 | 44.2% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (24) accuracy | 79.2% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 0.0% |

Turns judged: 5 (5 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 5.

### `claude-code (sonnet)`

Scored on partial: 1 run(s) of 43 of 43 cases; runs finished: cc-metricflow 43 of 129; model responses spent: cc-metricflow 47.

| | `cc-metricflow` |
|---|---|
| Accuracy | 51.2% |
| Confident-wrong | 30.2% |
| pass^1 | 51.2% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (24) accuracy | 91.7% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 0.0% |

Turns judged: 1 (1 the code left unclear, 0 confident-wrong with a hedge outside the list); verdicts that stood: 1.

### `claude-code (opus)`

Scored on partial: 1 run(s) of 43 of 43 cases; runs finished: cc-metricflow 43 of 129; model responses spent: cc-metricflow 47.

| | `cc-metricflow` |
|---|---|
| Accuracy | 53.5% |
| Confident-wrong | 25.6% |
| pass^1 | 53.5% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (24) accuracy | 91.7% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 5.3% |

### `claude-code (fresh-haiku)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 129 of 129; model responses spent: cc-metricflow 141.

| | `cc-metricflow` |
|---|---|
| Accuracy | 54.3% |
| Confident-wrong | 7.0% |
| pass^3 | 48.8% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (24) accuracy | 86.1% |
| `trap` (6) accuracy | 94.4% |
| `uncovered` (19) accuracy | 14.0% |

### `claude-code (fresh-sonnet)`

Scored on all 3 runs of every case; runs finished: cc-metricflow 129 of 129; model responses spent: cc-metricflow 141.

| | `cc-metricflow` |
|---|---|
| Accuracy | 50.4% |
| Confident-wrong | 12.4% |
| pass^3 | 48.8% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (24) accuracy | 83.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 8.8% |

### `claude-code (fresh-opus)`

Scored on partial: 1 run(s) of 43 of 43 cases; runs finished: cc-metricflow 43 of 129; model responses spent: cc-metricflow 47.

| | `cc-metricflow` |
|---|---|
| Accuracy | 51.2% |
| Confident-wrong | 7.0% |
| pass^1 | 51.2% |
| `conversation` (8) accuracy | 62.5% |
| `covered` (24) accuracy | 83.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 10.5% |

Turns judged: 1 (0 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 0.
Confident-wrong turns the judge moved: 1 of 1 (0 to wrong, hedged; 1 to unclear).

Turns still unclear after judging (counted as wrong):

- `cc-metricflow` `hard_refund_rate_by_value` run 1 turn 1: declined / wrong

### `google-data-agent (MODEL_UNSPECIFIED)`

Scored on partial: 1 run(s) of 43 of 43 cases; runs finished: native-bare 129 of 129, native-context-bare 129 of 129, native-context 129 of 129, native-governed 129 of 129, native-graph 129 of 129, native-kc-max 128 of 129, native-kc-reach 129 of 129, native-kc 129 of 129, native-shaped 129 of 129; model responses spent: native-bare 141, native-context-bare 141, native-context 142, native-governed 141, native-graph 141, native-kc-max 138, native-kc-reach 141, native-kc 141, native-shaped 141.

| | `native-bare` | `native-context-bare` | `native-context` | `native-governed` | `native-graph` | `native-kc-max` | `native-kc-reach` | `native-kc` | `native-shaped` |
|---|---|---|---|---|---|---|---|---|---|
| Accuracy | 62.8% | 90.7% | 90.7% | 72.1% | 55.8% | 86.0% | 83.7% | 62.8% | 60.5% |
| Confident-wrong | 32.6% | 0.0% | 0.0% | 0.0% | 18.6% | 2.3% | 9.3% | 14.0% | 14.0% |
| pass^1 | 62.8% | 90.7% | 90.7% | 72.1% | 55.8% | 86.0% | 83.7% | 62.8% | 60.5% |
| `conversation` (8) accuracy | 62.5% | 50.0% | 50.0% | 62.5% | 50.0% | 37.5% | 62.5% | 50.0% | 37.5% |
| `covered` (24) accuracy | 62.5% | 83.3% | 83.3% | 87.5% | 62.5% | 79.2% | 83.3% | 66.7% | 54.2% |
| `trap` (6) accuracy | 50.0% | 100.0% | 100.0% | 100.0% | 33.3% | 100.0% | 83.3% | 50.0% | 50.0% |
| `uncovered` (19) accuracy | 63.2% | 100.0% | 100.0% | 52.6% | 47.4% | 94.7% | 84.2% | 57.9% | 68.4% |

Turns judged: 14 (7 the code left unclear, 7 confident-wrong with a hedge outside the list); verdicts that stood: 14.
Confident-wrong turns the judge moved: 1 of 7 (1 to wrong, hedged; 0 to unclear).

### `google-data-agent (LATEST_GA_MODEL)`

Scored on partial: 1 run(s) of 42 of 43 cases; runs finished: native-context-bare 128 of 129; model responses spent: native-context-bare 140.

| | `native-context-bare` |
|---|---|
| Accuracy | 92.9% |
| Confident-wrong | 2.4% |
| pass^1 | 92.9% |
| `conversation` (7) accuracy | 71.4% |
| `covered` (23) accuracy | 91.3% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 94.7% |

Turns judged: 1 (0 the code left unclear, 1 confident-wrong with a hedge outside the list); verdicts that stood: 1.
Confident-wrong turns the judge moved: 0 of 1 (0 to wrong, hedged; 0 to unclear).

### `google-data-agent (MODEL_UNSPECIFIED, THINKING)`

Scored on partial: 2 run(s) of 43 of 43 cases; runs finished: native-context-bare 128 of 129; model responses spent: native-context-bare 140.

| | `native-context-bare` |
|---|---|
| Accuracy | 94.2% |
| Confident-wrong | 0.0% |
| pass^2 | 93.0% |
| `conversation` (8) accuracy | 68.8% |
| `covered` (24) accuracy | 89.6% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 100.0% |

### `google-data-agent (MODEL_UNSPECIFIED, FAST)`

Scored on partial: 2 run(s) of 43 of 43 cases; runs finished: native-context-bare 128 of 129; model responses spent: native-context-bare 140.

| | `native-context-bare` |
|---|---|
| Accuracy | 95.3% |
| Confident-wrong | 0.0% |
| pass^2 | 95.3% |
| `conversation` (8) accuracy | 75.0% |
| `covered` (24) accuracy | 91.7% |
| `trap` (6) accuracy | 100.0% |
| `uncovered` (19) accuracy | 100.0% |

### The rule across models

The managed best (RULE.md § The rule, 1): `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, accuracy 94.6%.
Each arm of ours on each model it ran with, paired by case against it on the cases both reached (each case's share over its finished runs), percentile bootstrap 95% (10,000 resamples, seed 325); ours on `nvidia/nemotron-3.5-super-vl:free` decides (RULE.md § The rule, 2), ours on any other model is the check on whether a gap is the model's:

- `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.209 [-0.326, -0.101], confident-wrong +0.093 [+0.023, +0.178]: not worth building (the check; 129 runs finished).
- `custom-hybrid` (rung 4) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.132 [-0.240, -0.039], confident-wrong +0.031 [+0.000, +0.085]: not worth building (the check; 129 runs finished).
- `custom-toolbox` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.496 [-0.643, -0.349], confident-wrong +0.070 [+0.008, +0.147]: not worth building (the check; 129 runs finished).
- `native-mcp` (rung 3) on `claude-haiku-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.132 [-0.225, -0.054], confident-wrong +0.062 [+0.016, +0.132]: not worth building (the check; 129 runs finished).
- `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.372 [-0.519, -0.233], confident-wrong +0.054 [+0.000, +0.124]: not worth building (the check; 129 runs finished).
- `custom-toolbox` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.465 [-0.620, -0.318], confident-wrong +0.070 [+0.008, +0.147]: not worth building (the check; 129 runs finished).
- `native-mcp` (rung 3) on `claude-sonnet-5-5` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.050 [-0.116, +0.000], confident-wrong +0.000 [+0.000, +0.000]: not worth building (the check; 87 runs finished).
- `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.209 [-0.318, -0.109], confident-wrong +0.070 [+0.023, +0.124]: not worth building (decides; 129 runs finished).
- `custom-hybrid` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.085 [-0.186, -0.008], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 43 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.504 [-0.651, -0.357], confident-wrong +0.186 [+0.070, +0.302]: not worth building (the check; 43 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.434 [-0.581, -0.287], confident-wrong +0.302 [+0.163, +0.442]: not worth building (the check; 43 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.411 [-0.558, -0.264], confident-wrong +0.256 [+0.140, +0.395]: not worth building (the check; 43 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-haiku)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.403 [-0.543, -0.271], confident-wrong +0.070 [+0.016, +0.132]: not worth building (the check; 129 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-sonnet)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.442 [-0.589, -0.302], confident-wrong +0.124 [+0.047, +0.217]: not worth building (the check; 129 runs finished).
- `cc-metricflow` (rung 4) on `claude-code (fresh-opus)` against `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 43 of 43 cases: accuracy -0.434 [-0.581, -0.295], confident-wrong +0.070 [+0.000, +0.163]: not worth building (the check; 43 runs finished).
- The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-hybrid`: the same verdict on every model, so the gap is not the model's.
- The check on `custom-toolbox`: the same verdict on every model, so the gap is not the model's.
- The check on `native-mcp`: the same verdict on every model, so the gap is not the model's.
- The check on `cc-metricflow`: the same verdict on every model, so the gap is not the model's.

### The rule on both sets

RULE.md § Changes since freezing (#356): each set goes through the rule on its own; an arm of ours is worth building only if step 2 holds on both sets, and where they disagree the cheaper rung wins, as a tie does.
- The managed best on the frozen set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 94.1%.
- The managed best on the hard set: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`, 94.6%.
- `custom-metricflow` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-hybrid` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-lightdash` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `native-mcp` on `nvidia/nemotron-3.5-super-vl:free` (decides): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `custom-metricflow` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-hybrid` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-toolbox` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `native-mcp` on `claude-haiku-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-metricflow` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-toolbox` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `native-mcp` on `claude-sonnet-5-5` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `custom-metricflow` on `claude-opus-5-5` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- `cc-metricflow` on `claude-code (haiku)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (sonnet)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (opus)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-haiku)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-sonnet)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (fresh-opus)` (the check): the frozen set: not worth; the hard set: not worth; on both sets: not worth building.
- `cc-metricflow` on `claude-code (subject-haiku)` (the check): the frozen set: not worth; the hard set: not paired yet; on both sets: undecided until it is paired on both sets.
- Step 3 (RULE.md § The rule, 3; it applies when no arm of ours is worth building): the arms with no accuracy difference from the managed best on both sets: `native-mcp` on `claude-sonnet-5-5` (rung 3), `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)` (rung 1).
  The cheapest rung among them is 1: `native-context-bare` on `google-data-agent (MODEL_UNSPECIFIED, THINKING)`; within a rung the arm with fewer moving parts named in its finding wins (§ The cost ladder), which the report names.
