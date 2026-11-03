# The frozen set on Claude, first pass: Haiku on `custom-metricflow` (#365)

Issue [#365](../../../../../../issues/365), part of [Map #324](../../../../../../issues/324), on the budget plan of [#361](../../../../../../issues/361) ([the runner's finding](2026-11-03-361-claude-in-the-runner.md#the-plan-by-question-set-revised-by-the-probe)).

## The question

Does an arm of ours, on Claude, change what the rule's cross-model comparison (#333's option C, [#359](2026-11-03-359-cross-model.md)) says about the managed best, and what does each pass cost against the plan?

## Stopped by the owner's anomaly check

- The first pass, Haiku on `custom-metricflow`, finished all 288 case-runs inside its budget ($0.4346 of $1.00), and its ledger row fired the owner's token check twice (`measured`, [the ledger](2026-11-03-361-claude-spend.md), 2026-11-03T21:05Z):
  > a case-run of 96419 tokens on claude-haiku-5-5, over 3 x the probe's per-case median (25001.5); a case-run of 93995 tokens on claude-haiku-5-5, over 3 x the probe's per-case median (25001.5)
- Both are `bet_applicants_reaching_interview` (an `uncovered` case), runs 1 and 2: 7 model calls each, $0.0050 and $0.0050; run 3 took 72,235 tokens in 6 calls.
  The agent kept querying the recruitment metrics for a stage history the layer does not hold, then answered with a range or declined.
- The largest single call of the pass was 20,446 tokens, below the check's line (75,004); no billing error, no `credit balance` error, no 429, no key refusal, no failed call in the pass.
- Per the lane's orders, any anomaly stops all Claude work for the session: `baseline` on Haiku, Sonnet on `custom-metricflow`, and the GCP passes were not started.
- What the check measures: the probe's median comes from ten cases, none of them a multi-step `uncovered` lookup; on this pass the per-case-run median is 25,443 tokens (close to the probe's) and the five largest are all `uncovered` or hour-of-day cases at 6 to 7 calls.

## What was run (measured)

- 2026-11-03T20:42Z: a free `GET /v1/models` with `BET_ANTHROPIC_API_KEY` sent as a header from a process substitution answered 200, 14 models, `claude-haiku-5-5`, `claude-sonnet-5-5` and `claude-opus-5-5` among them (a ledger row, $0).
- The catalog rebuilt in the worktree by `dbt parse`, `scripts/build_catalog.py` and `scripts/check_catalog.py` against `dbt_dev` (no database write), under `flock -s` on the warehouse lock.
- 2026-11-03T20:43Z to 21:05Z, from `services/semantic-agent`, under `flock -s` on the warehouse lock, with `DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=dbt_dev DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics MODEL_RETRIES=4 MODEL_BACKEND=anthropic MODEL_ID=claude-haiku-5-5` and no `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`:
  `python -m semantic_agent.bet_eval --runs 3 --arms custom-metricflow --dollars 1.00 --label "#365 haiku custom-metricflow"`.
- Runs logged to the scored log [`eval-local.jsonl`](../eval-local.jsonl) (288, each with its `usage`); every call to [the calls log](2026-11-03-361-claude-calls.jsonl) (962); the pass's row to [the ledger](2026-11-03-361-claude-spend.md).
- 2026-11-03T21:07Z: `eval.md` and `eval-local.md` regenerated with `DBT_DBNAME=dbt_dev python -m semantic_agent.bet_eval --report-only` (no request sent).

## The pass (measured)

`custom-metricflow` on `claude-haiku-5-5`, all 3 runs of all 96 cases, the blind judge not yet asked about its turns:

| | `custom-metricflow` on Haiku |
|---|---|
| Accuracy | 77.8% |
| Confident-wrong | 2.4% |
| pass^3 | 71.9% |
| `conversation` (7) accuracy | 95.2% |
| `covered` (67) accuracy | 92.5% |
| `distractor` (3) accuracy | 100.0% |
| `planted` (4) accuracy | 100.0% |
| `trap` (11) accuracy | 97.0% |
| `uncovered` (29) accuracy | 43.7% |
| Model calls | 962 |
| Dollars | $0.4346 (median $0.0015 a case-run, max $0.0050) |

- Run outcomes: 224 right, 30 declined, 17 wrong, 10 unclear, 7 confident-wrong.
- The confident-wrong runs: `calls_about_returns` (runs 1 and 3), `bet_customers_september`, `bet_customers_over_three_orders`, `median_order_value`, `bet_applicants_reaching_interview` and `objection_rate` (one run each).
  `bet_applicants_reaching_interview` run 2 answers "at least 67% … I can't tell whether that rejection came before or after interview": a hedge outside the list, so it waits for the judge, which may move it.
- The 10 unclear turns count as wrong until judged; all 10 are on this pass (e.g. `partners_engaged_one_day`, "Two partners replied", whose number is a word).
- Dollars by group, per case-run (a case can be in several groups): `conversation` $0.0012, `covered` $0.0014, `trap` $0.0014, `distractor` $0.0015, `planted` $0.0017, `uncovered` $0.0017.
- The plan expected $0.42 for this pass at the probe's median and gave it $1: it cost $0.4346.
- On the 47 cases the free model's `custom-metricflow` reached (run 1, nearly all `covered`), Haiku's run 1 has 42 right against the free model's 45: Haiku confident-wrong on `calls_about_returns`, wrong where the free model declined on `median_order_value`, unclear on `partners_engaged_one_day` and `candidates_in_interview_as_of`.

## What the cross-model check says (measured, `eval.md` at this branch's head)

> - `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`, 47 of 96 cases: accuracy +0.011 [-0.053, +0.064], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 47 runs finished).
> - `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy -0.092 [-0.168, -0.017], confident-wrong -0.038 [-0.094, +0.010]: not worth building (the check; 288 runs finished).
> - The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.

- On all 96 cases, Haiku's `custom-metricflow` is below the managed best in accuracy (the interval excludes zero) and shows no confident-wrong difference: the verdict "not worth building" holds on a second model.
- The accuracy gap sits in `uncovered` (43.7% against `native-context`'s 69.0%), where the semantic layer declines by design (RULE.md § Scoring a run) and the data agent writes SQL over the raw tables.
- It is the check on one model only: `native-context` has run 1 of all 96 and part of run 2, the free model's pair holds 47 cases, and the judge has not decided the 10 unclear turns, which can only raise Haiku's accuracy.
- Haiku is the plan's cheapest model; Sonnet on `custom-metricflow` (pass 3) is the check that separates "the model is weak" from "the layer declines".

## What stays unknown

- `baseline`, `custom-toolbox` and `native-mcp` on Haiku, Sonnet on `custom-metricflow` and `native-mcp`, and the `native-mcp` cost probe: not run, stopped by the anomaly check.
- The judge's verdicts on the 10 unclear Haiku turns: 10 new undecided turns, not fewer than 10, so the judge was not asked (34 turns across all logs await it; OpenRouter's free quota is nearly spent until 00:00Z).
- Whether the token check should hold for `uncovered` cases: the owner decides (the lane's report asks).

## Also in this change

- `probes/328_mcp_live.py` takes `--dollars` and `--label` on Claude: it opens a metered pass (`spend.METER.start`), stops before a case-run that would cross the budget, and appends the ledger row with the anomaly checks (`spend.finish_pass`), as `bet_eval` does; the live arms' Claude passes needed it, since the probe never opened a pass.
- `semantic_agent/agent.py` builds `root_agent` on first use (PEP 562 `__getattr__`), so importing the package builds no model: before, `python -m semantic_agent.bet_eval` with `MODEL_BACKEND=anthropic` and no key died at import with a `MissingKey` traceback (exit 1) instead of the documented skip (exit 3), since the in-process test imported the package under another backend (`measured`, 2026-11-03T21:10Z; `test_the_command_line_skips_a_claude_pass_without_its_key` fails before the change and passes after).

## Sources

- [`eval.md`](../eval.md), [`eval-local.jsonl`](../eval-local.jsonl), [the calls log](2026-11-03-361-claude-calls.jsonl) and [the ledger](2026-11-03-361-claude-spend.md) at this branch's head (`measured`).
- Prices: [the runner's finding](2026-11-03-361-claude-in-the-runner.md#prices-used-stated) (`stated`, Anthropic's pricing page read 2026-11-03).
