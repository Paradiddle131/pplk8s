# The frozen set on Claude: Haiku on both local arms, Sonnet on `custom-metricflow` cut short (#365)

Issue [#365](../../../../../../issues/365), part of [Map #324](../../../../../../issues/324), on the budget plan of [#361](../../../../../../issues/361) ([the runner's finding](2026-11-03-361-claude-in-the-runner.md#the-plan-by-question-set-revised-by-the-probe)).

## The question

Does an arm of ours, on Claude, change what the rule's cross-model comparison (#333's option C, [#359](2026-11-03-359-cross-model.md)) says about the managed best, and what does each pass cost against the plan?

## Stops and anomalies, first

- **The Console check (2026-11-03, the orchestrator, about 21:59Z):** the owner's Console showed $94.55 of credits left, read against the ledger's $1.2520 of 21:05Z; the orchestrator stopped all Claude calls, and the Sonnet pass was aborted at 21:59:48Z (SIGINT, 170 of 288 runs logged).
  - The metered running total, summed from [the calls log](2026-11-03-361-claude-calls.jsonl) by timestamp, crossed $5.45 (the Console's $100.00 minus $94.55) at 21:58:32Z: the two passes run after 21:05Z (Haiku `baseline` from 21:15Z, Sonnet `custom-metricflow` from 21:44Z) had spent $4.56 by then (`measured`).
  - So the Console matches the meter at the time it was read: no spend outside the runner shows; the gap came from reading the Console against the ledger's 21:05Z total while two passes were running.
  - Billed but not metered, at most: the one Sonnet call in flight at the abort (cut by `CancelledError`, no usage returned), a typical Sonnet call of this pass being about $0.01 to $0.04.
  - After the abort, the Console should show about $94.19 left ($100.00 minus $5.8120), or a few cents less for that call.
- **The owner's token check** ("a case-run over three times the probe's per-case median on its model") fired on three case-runs, all `bet_applicants_reaching_interview` (an `uncovered` case):
  - Haiku `custom-metricflow` run 1, 96,419 tokens, $0.0050, and run 2, 93,995 tokens, $0.0050 (7 calls each); it stopped the first session's Claude work.
  - Sonnet `custom-metricflow` run 1, 87,121 tokens, $0.0626, 7 calls.
  - The orchestrator's interim rule for the second session (2026-11-03T21:15Z): the check runs and is reported, and stops the lane only for a case-run over 10x the probe's median dollars on its model (Haiku $0.015, Sonnet $0.25, Opus $0.53); none came near it (Haiku max $0.0050 and $0.0023, Sonnet max $0.0626).
  - The agent kept querying the recruitment metrics for a stage history the layer does not hold, then answered with a range or declined.
- No billing or `credit balance` error, no 429, no key refusal, no failed call on any pass; the largest single call was 20,446 tokens (Haiku), 17,339 (Sonnet).

## The prices checked (stated)

- Anthropic's pricing page, <https://platform.claude.com/docs/en/about-claude/pricing.md>, read again 2026-11-03 between 21:59Z and 22:02Z, USD per million tokens (input, 5-minute cache write, cache read, output): Haiku 5.5 up to 100,000 prompt tokens 0.10, 0.125, 0.01, 0.50 (over: 0.50, 0.625, 0.05, 2.50); Sonnet 5.5 2.00, 2.50, 0.10, 10.00; Opus 5.5 4.00, 5.00, 0.20, 20.00.
  `spend.PRICES` matches every one.
- The page's footnote: "Cache hits and refreshes on Claude Opus 5.5 and Claude Sonnet 5.5 are priced at 0.05x the base input price" ($0.10 on Sonnet 5.5).
- The `claude-api` skill (bundled 2.1.317, read 2026-11-03 between 21:59Z and 22:02Z) disagrees on one price: its Sonnet 5.5 line says "cache reads $0.20"; its prompt-caching notes give 0.05x only for Opus 5.5 and about 0.1x elsewhere.
  If the skill were right, the meter under-counts Sonnet by $0.10 a million cache-read tokens: 3,649,284 so far (the probe and this pass), $0.36; the ledger would be higher than the Console, not lower, so it does not explain a Console deficit.
- What else the meter could miss (read in the installed packages, 2026-11-03):
  - Thinking: Anthropic bills thinking as output and counts it in `usage.output_tokens`; LiteLLM 1.96.2 sets `completion_tokens` from `output_tokens` (`litellm/llms/anthropic/chat/transformation.py`, `calculate_usage`), and ADK's `LiteLlm` takes `candidates_token_count` from `completion_tokens` (`google/adk/models/lite_llm.py`), which `spend.usage_of` prices as output: thinking is metered.
  - Retries: `ClaudeLlm` records a call only when a final response carries usage; a LiteLLM retry (`MODEL_RETRIES=4`) after a client timeout (120 s) or a dropped connection would leave the first attempt's server-side work unmetered if Anthropic billed it.
    No retry, timeout or API error appears in the passes' logs; LiteLLM's `completion()` lines number 960 and 560 against 962 and 561 metered calls on the two `custom-metricflow` passes (the `baseline` agent logs none), so no extra request shows.
  - Failed calls: a call that raises is kept in the pass's `failures` only, not in the calls log; none failed.
  - `inference_geo` (a 1.1x multiplier) is never set; no 1-hour cache writes are written.

## What was run (measured)

- 2026-11-03T20:42Z and 21:15Z: free `GET /v1/models`, the key sent as a header from a process substitution: 200, 14 models, the three above among them (two ledger rows, $0).
- The catalog rebuilt in the worktree by `dbt parse`, `scripts/build_catalog.py` and `scripts/check_catalog.py` against `dbt_dev` (no database write), under `flock -s` on the warehouse lock.
- From `services/semantic-agent`, under `flock -s` on the warehouse lock, with `DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=dbt_dev DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics MODEL_RETRIES=4 MODEL_BACKEND=anthropic` and no `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`, `python -m semantic_agent.bet_eval --runs 3 --arms <arm> --dollars <budget> --label <pass>`:
  - 20:43Z to 21:05Z, `MODEL_ID=claude-haiku-5-5`, `custom-metricflow`, $1.00: done.
  - 21:15Z to 21:42Z, `MODEL_ID=claude-haiku-5-5`, `baseline`, $1.00: done.
  - 21:43Z to 21:59Z, `MODEL_ID=claude-sonnet-5-5`, `custom-metricflow`, $10.00: aborted at 21:59:48Z, its last call at 21:59:44Z; its ledger row written by hand from the calls log, since the cut pass never reached `spend.finish_pass`.
- Runs logged to the scored log [`eval-local.jsonl`](../eval-local.jsonl), each with its `usage`; every call to [the calls log](2026-11-03-361-claude-calls.jsonl); each pass's row to [the ledger](2026-11-03-361-claude-spend.md).
- `eval.md` and `eval-local.md` regenerated after each pass with `DBT_DBNAME=dbt_dev python -m semantic_agent.bet_eval --report-only` (no request sent), the judge's cached verdicts applied.

## The passes (measured, `eval.md` at this branch's head, the judge not yet asked about these turns)

| | `custom-metricflow`, Haiku | `baseline`, Haiku | `custom-metricflow`, Sonnet (partial) |
|---|---|---|---|
| Runs scored | 3 of every case | 3 of every case | run 1 of every case (170 of 288 finished) |
| Accuracy | 77.8% | 61.1% | 76.0% |
| Confident-wrong | 2.4% | 10.4% | 1.0% |
| pass^k | pass^3 71.9% | pass^3 56.2% | pass^1 76.0% |
| `conversation` (7) | 95.2% | 57.1% | 100.0% |
| `covered` (67) | 92.5% | 71.6% | 98.5% |
| `distractor` (3) | 100.0% | 100.0% | 100.0% |
| `planted` (4) | 100.0% | 100.0% | 100.0% |
| `trap` (11) | 97.0% | 66.7% | 100.0% |
| `uncovered` (29) | 43.7% | 36.8% | 24.1% |
| Model calls | 962 | 1,038 | 561 |
| Dollars | $0.4346 | $0.2218 | $4.3382 |
| A case-run, median (max) | $0.0015 ($0.0050) | $0.0007 ($0.0023) | $0.0254 ($0.0626) |
| Plan's expectation (budget) | $0.42 ($1) | $0.63 ($1) | $7.26 ($10) for 288 |

- Paired by case on Haiku, `custom-metricflow` minus `baseline`: accuracy +0.167 [+0.069, +0.264], confident-wrong -0.080 [-0.139, -0.024], both a difference (descriptive, RULE.md § The rule, 5).
- Dollars a case-run by group (a case can be in several): Haiku `custom-metricflow` $0.0012 (`conversation`) to $0.0017 (`planted`, `uncovered`); Haiku `baseline` $0.0005 (`planted`) to $0.0011 (`distractor`); Sonnet $0.0178 (`conversation`) to $0.0285 (`planted`).
- Confident-wrong runs:
  - Haiku `custom-metricflow` (7): `calls_about_returns` runs 1 and 3, `bet_customers_september`, `bet_customers_over_three_orders`, `median_order_value`, `bet_applicants_reaching_interview`, `objection_rate`.
  - Haiku `baseline` (30): across 15 cases, `shipped_orders`, `damaged_returns`, `signups_september`, `return_rate_september`, `outreach_reply_rate` and `bet_delivery_calls_per_100_shipped` in all three runs.
  - Sonnet `custom-metricflow` (2): `calls_about_returns` runs 1 and 2.
- Unclear turns, counted wrong until judged: Haiku `custom-metricflow` 10, Haiku `baseline` 1, Sonnet 5; 12 of Haiku `baseline`'s confident-wrong turns carry a hedge outside the list and await the judge too, so its 10.4% may fall.
- Sonnet answers almost every covered case (98.5%) and declines more uncovered ones than Haiku (24.1% against 43.7% right), so on run 1 its accuracy is Haiku's within two points with fewer confident-wrong turns.

## What the cross-model check says (measured, `eval.md` at this branch's head)

> - `custom-metricflow` (rung 4) on `nvidia/nemotron-3.5-super-vl:free` against `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`, 47 of 96 cases: accuracy +0.011 [-0.053, +0.064], confident-wrong +0.000 [+0.000, +0.000]: not worth building (decides; 47 runs finished).
> - `custom-metricflow` (rung 4) on `claude-haiku-5-5` against `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy -0.092 [-0.168, -0.017], confident-wrong -0.038 [-0.094, +0.010]: not worth building (the check; 288 runs finished).
> - `custom-metricflow` (rung 4) on `claude-sonnet-5-5` against `native-context` on `google-data-agent (MODEL_UNSPECIFIED)`, 96 of 96 cases: accuracy -0.120 [-0.208, -0.036], confident-wrong -0.052 [-0.104, +0.000]: not worth building (the check; 170 runs finished).
> - The check on `custom-metricflow`: the same verdict on every model, so the gap is not the model's.

- On all 96 cases, ours on both Claude models is below the managed best in accuracy (both intervals exclude zero), and its confident-wrong difference stays inside zero: "not worth building" holds on the free model, Haiku and Sonnet alike.
- The gap is the `uncovered` group, where the semantic layer declines by design (RULE.md § Scoring a run) and `native-context` (69.0% there) writes SQL over the raw tables; a stronger model declines more, not less, so the gap is the layer's, not the model's.
- Sonnet's line is on run 1 of every case and part of run 2, and `native-context` holds run 1 of all 96 and part of run 2; the judge has not decided the 16 new unclear turns of ours, which can only raise our accuracy.
- `baseline` is on no rung and stays out of the rule's comparison.

## What stays unknown

- Sonnet `custom-metricflow`'s other 118 runs (runs 2 and 3), resumable from the log at about $3.0 more (its median $0.0254 a case-run).
- `custom-toolbox` and `native-mcp` on Haiku, Sonnet on `native-mcp`, and the `native-mcp` cost probe: not run (the GCP lock is held by the data-agent lanes, and the Console check stopped all Claude work).
- The judge's verdicts on the 28 new turns that await it (16 unclear, 12 hedged confident-wrong on `baseline`): not asked, since 10 or more new undecided turns exist and OpenRouter's free quota is nearly spent until 00:00Z.
- Which of the two Sonnet 5.5 cache-read prices Anthropic bills: the Console's per-model cost view or the Admin API's cost report (owner-only) would settle it.

## Also in this branch

- `probes/328_mcp_live.py` takes `--dollars` and `--label` on Claude: it opens a metered pass (`spend.METER.start`), stops before a case-run that would cross the budget, and appends the ledger row with the anomaly checks (`spend.finish_pass`), as `bet_eval` does (merged with the first pass).
- `semantic_agent/agent.py` builds `root_agent` on first use (PEP 562 `__getattr__`), so a Claude pass without its key is skipped with that reason (exit 3), not a `MissingKey` traceback at import (merged with the first pass; `test_the_command_line_skips_a_claude_pass_without_its_key`).

## Sources

- [`eval.md`](../eval.md), [`eval-local.jsonl`](../eval-local.jsonl), [the calls log](2026-11-03-361-claude-calls.jsonl) and [the ledger](2026-11-03-361-claude-spend.md) at this branch's head (`measured`).
- Anthropic's pricing page, <https://platform.claude.com/docs/en/about-claude/pricing.md>, read 2026-11-03 between 21:59Z and 22:02Z (`stated`).
- The `claude-api` skill's model table and prompt-caching notes, bundled 2.1.317, read 2026-11-03 between 21:59Z and 22:02Z (`stated`).
- LiteLLM 1.96.2 `litellm/llms/anthropic/chat/transformation.py` and ADK's `google/adk/models/lite_llm.py`, as installed in `services/semantic-agent/.venv` (`stated`, read 2026-11-03).
