# Claude in the runner: the key, a cost probe and the budget plan by question set

Issue [#361](../../../../../../issues/361), part of [Map #324](../../../../../../issues/324).

## The question

What does a case-run of the frozen set cost on Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5, and which Claude passes fit the owner's $100.00 of credits with at least $10 kept back?

## What was built (measured by the tests below)

- `MODEL_BACKEND=anthropic` in `services/semantic-agent/src/semantic_agent/model.py`, still the only place that builds a model: ADK's `LiteLlm` on `anthropic/<model>`, the key passed explicitly from `BET_ANTHROPIC_API_KEY` and the base URL `https://api.anthropic.com` passed explicitly, so LiteLLM never falls back to `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` or the session's `ANTHROPIC_BASE_URL`.
- Only `claude-haiku-5-5`, `claude-sonnet-5-5` and `claude-opus-5-5` are allowed; any `claude-fable-*` is refused by name; a missing key raises `MissingKey`, and `bet_eval` prints `skipped: BET_ANTHROPIC_API_KEY is unset: the Claude passes are skipped` and exits 3.
- Prompt caching: LiteLLM's `cache_control_injection_points` on the system message (Anthropic renders tools before system, so that breakpoint caches the tool definitions and the instruction) and on the last message (the conversation so far, for the turn's next call).
- `max_tokens` 16,000 per call (adaptive thinking stays at each model's default effort: medium on Haiku and Opus, high on Sonnet).
- `semantic_agent/spend.py`: prices each call's `usage` (uncached input, output, cache reads, cache writes), logs every call to [`2026-11-03-361-claude-calls.jsonl`](2026-11-03-361-claude-calls.jsonl), refuses a call the pass's budget cannot cover (estimated at the dearest call of the pass on that model, before any at 12k input and 2k output), and appends each pass's row, with the anomaly checks, to [the spend ledger](2026-11-03-361-claude-spend.md).
- `bet_eval` takes `--dollars`, `--label`, `--arms` and `--log`; before each case-run it stops the pass when a case-run as dear as its dearest so far would cross the budget, and each logged run carries `model` and `usage` (tokens and dollars); `bet_live.run_live` logs the same `usage` and stops with `budget` (its caller opens and closes the pass); `make agent-eval ARM=bet DOLLARS=<n> LABEL=<pass>` passes both on.
- A `credit balance` or billing refusal is its own failure kind (`billing`) and ends the pass like a refused key; anything shaped like an Anthropic key is cut from error text before it is logged.
- Tests with a local stand-in for `/v1/messages` and scripted models, no network (`tests/test_claude.py`, 17): the explicit key and base URL reach the request (`x-api-key` is the test key, the path `/v1/messages`, the session's `ANTHROPIC_BASE_URL` pointed at a closed port is never used, `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` never read from the environment); the system block carries `cache_control`; Fable and unpriced models refused; the missing-key skip; pricing from stub usage on all three models and Haiku's long-context tier; a call the budget cannot cover never sent; the runner's budget stop; each anomaly check; the ledger row.

## Prices used (stated)

From Anthropic's pricing page, <https://platform.claude.com/docs/en/about-claude/pricing>, read 2026-11-03, USD per million tokens:

| Model | Input | 5-minute cache write | Cache read | Output |
|---|---|---|---|---|
| `claude-haiku-5-5` (prompt up to 100,000 tokens) | 0.10 | 0.125 | 0.01 | 0.50 |
| `claude-haiku-5-5` (prompt over 100,000 tokens) | 0.50 | 0.625 | 0.05 | 2.50 |
| `claude-sonnet-5-5` | 2.00 | 2.50 | 0.10 | 10.00 |
| `claude-opus-5-5` | 4.00 | 5.00 | 0.20 | 20.00 |

- Input and output match #361's body; Sonnet 5.5's cache read is $0.10 on the page (0.05x its input), not the body's $0.20, and the `claude-api` skill's cached model table agrees with the body's other prices; the runner uses the page.
- Cache writes are 1.25x input for the 5-minute TTL (the page and the skill agree); the runner writes no 1-hour entries.
- Haiku 5.5's long-context tier never applied in the probe (the largest prompt was about 14.6k tokens).

## The key (measured)

- 2026-11-03T19:50Z, the orchestrator: a free `GET /v1/models` answered 200 and listed `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`.
- 2026-11-03T20:06Z, this lane, before the first paid call: `curl https://api.anthropic.com/v1/models` with the key sent as a header from a process substitution answered 200, 14 models, the three above among them.

## The cost probe (measured)

- Run 2026-11-03T20:17Z to 20:21Z: `custom-metricflow` (the semantic agent on its MetricFlow tools) on the Compose warehouse's `dbt_dev` fixture, local, no GCP; the warehouse lock held shared while it read (the catalog was rebuilt in the worktree by `dbt parse` and `scripts/build_catalog.py` only, no database write).
- Ten frozen cases, one run each, the same ten on every model, spread over the groups: `revenue_total` (covered, trap), `cost_per_booking_total` (covered, trap, distractor), `bet_top_country_september` (covered, distractor), `median_order_value`, `bet_median_days_to_hire`, `bet_istanbul_warmer` (uncovered), `followup_by_country`, `followup_how_computed`, `ambiguous_sales` (conversation, two turns each), `planted_campaign_top_spend` (planted).
- Command per model: `MODEL_BACKEND=anthropic MODEL_ID=<model> python -m semantic_agent.bet_eval --runs 1 --arms custom-metricflow --log docs/research/semantic-bet/findings/2026-11-03-361-cost-probe.jsonl --dollars <cap> --label "probe <model>" <the ten ids>` under `flock -s` on the warehouse lock; caps Haiku $1 (a one-case smoke at $0.20, then $0.99), Sonnet $4, Opus $5; no pass came near its cap.
- The runs: [`2026-11-03-361-cost-probe.jsonl`](2026-11-03-361-cost-probe.jsonl) (30, kept out of the scored eval logs); every call: [the calls log](2026-11-03-361-claude-calls.jsonl) (102).

Per case-run, on the ten cases:

| Model | Dollars, median | Dollars, max | Tokens, median | Tokens, max | Calls, median (max) | Output tokens, median (max) | The probe's total |
|---|---|---|---|---|---|---|---|
| `claude-haiku-5-5` | $0.0015 | $0.0020 | 25,001 | 50,433 | 3 (5) | 574 (798) | $0.0148 |
| `claude-sonnet-5-5` | $0.0252 | $0.0328 | 24,903 | 47,719 | 3 (5) | 319 (765) | $0.2525 |
| `claude-opus-5-5` | $0.0526 | $0.0798 | 24,938 | 60,289 | 3 (6) | 428 (831) | $0.5500 |

- The probe cost $0.8173 in all, against its $10 cap.
- Most input is cached: on Sonnet, 192,367 cache-read and 77,934 cache-write tokens against 90 uncached input tokens; the first call of the pass writes the 3,093-token stable prefix (tools and instruction), every later case reads it.
- Cache writes are most of the bill (Sonnet: $0.195 of $0.2525), chiefly `list_metrics`' catalog (about 7k tokens) written once per case-run behind the question, since it sits after the question that changes; without caching the same tokens would cost about twice as much (Sonnet: about 25k input and 0.4k output a case-run at list price, $0.054 against $0.025).
- Outcomes, not scored for the verdict (one run, ten cases): Haiku 8 right, 1 declined, 1 confident-wrong (`median_order_value`); Sonnet 7 right, 3 declined; Opus 8 right, 2 declined.
- The plan's assumption (about 4 calls of about 12k input a case-run) was high: a case-run takes about 3 calls of about 8.3k tokens each, mostly cache.

## The anomaly checks (measured, after every pass)

None fired on any of the four probe passes: no pass over its budget, no call or case-run over three times the probe's per-case median on its model, no billing or `credit balance` error, no 429, no key refusal, the running total $0.8173, far below $80.

## The plan by question set (revised by the probe)

- A model is chosen per question set and given to every arm of ours on that set, so arms stay paired on one model within a set; never Fable.
- The probe measured `custom-metricflow` only: the other arms of ours are estimated from their logged tool calls on the free model (`baseline` a median of 4 model calls, max 13; `custom-toolbox` a median of 1 tool call; `native-mcp` a median of 8 tool calls, max 17, [silver only](2026-11-03-350-mcp-silver.jsonl)), so `native-mcp` is planned at 4x `custom-metricflow`'s median, `baseline` at 1.5x, `custom-toolbox` at 1x.
- The hard set ([#356](../../../../../../issues/356)) is planned at 50 cases (it needs at least 40) and 1.5x the frozen set's cost a case-run; scale its budgets by its real size.
- Each pass's budget is its `--dollars`; a pass stops before it crosses it, and a pass cut by its budget resumes in the next wake only if the plan's total still holds.

| # | Pass | Set, arm, model | Case-runs | Expected | Budget |
|---|---|---|---|---|---|
| 0 | The cost probe (done) | frozen, `custom-metricflow`, all three | 30 | measured | $0.82 spent |
| 1 | `native-mcp` cost probe: the same ten cases, k = 1, on each model (gates passes 4 and 7) | frozen, `native-mcp`, all three | 30 | $3.2 | $4 |
| 2 | Haiku on the frozen set, all four arms ([#365](../../../../../../issues/365)) | frozen, `custom-metricflow` / `baseline` / `custom-toolbox` / `native-mcp`, Haiku | 288 each | $0.42 / $0.63 / $0.42 / $1.67 | $1 / $1 / $1 / $3 |
| 3 | Sonnet on the frozen set, `custom-metricflow` (#365) | frozen, Sonnet | 288 | $7.26 | $10 |
| 4 | Sonnet on the frozen set, `native-mcp` (#365) | frozen, Sonnet | 288 | $29 | $30 |
| 5 | Haiku on the hard set, all four arms ([#364](../../../../../../issues/364)) | hard, Haiku | 150 each | $0.33 / $0.49 / $0.33 / $1.31 | $0.75 / $0.75 / $0.75 / $1.75 |
| 6 | The hard set's model on `custom-metricflow` (#364) | hard, Sonnet (Opus if pass 1 allows) | 150 | $5.7 (Opus $11.8) | $8 |
| 7 | The hard set's model on `native-mcp` (#364) | hard, Sonnet (Opus if pass 1 allows) | 150 | $22.7 (Opus $47) | $26 |
| | In all | | | $74.2 (with the probe spent) | $88.8 (with the probe spent) |
| | Kept back | | | | $11.2 |

- The gate after pass 1: with `native-mcp`'s measured cost a case-run, recompute passes 4 and 7; if the hard set's two arms fit on Opus (the owner's "Opus for the hard ones") with the frozen Sonnet passes and $10 still kept back, passes 6 and 7 run on Opus with the freed budget, else on Sonnet; the frozen set's passes come first, since the rule decides on it.
- Against #361's first plan ($86: Haiku frozen ~$8, Sonnet frozen ~$40, Opus hard ~$35, Haiku hard ~$3): the frozen set's passes keep their models and shrink to $46 (pass 1 aside); the hard set's pair moves to Sonnet unless `native-mcp` measures cheaper than 4x, because Opus on both hard arms at 4x would be about $59 alone.

## What it means for the verdict

- The Claude passes are cheap for our own MetricFlow arm (Sonnet about $7 and Opus about $15 for all 288 case-runs of the frozen set at the probe's median), so option C of [#333](../../../../../../issues/333) (whether a gap to the managed best is the model's) can be run on the frozen set within the budget.
- What decides the budget is `native-mcp`, whose many search and lookup calls are estimated, not measured: pass 1 measures it for about $4 before anything large runs.

## What stays unknown

- `native-mcp`, `baseline` and `custom-toolbox` on Claude: their cost is estimated from their tool calls on the free model, not measured (pass 1 measures `native-mcp`).
- The hard set's size and cost a case-run (#356 has not frozen it).
- Rate limits on this key: the probe met no 429 at one call every few seconds; a pass run beside another may.
- The credit balance itself: a regular key cannot read it; the owner compares the ledger's total with the Console (Billing).
- Effort: each model ran at its default effort; a lower effort would cut output and thinking tokens, and was not tried, so a pass stays comparable with the probe.

## Sources

- Anthropic pricing page, <https://platform.claude.com/docs/en/about-claude/pricing>, read 2026-11-03 (stated).
- The `claude-api` skill's prompt-caching notes: render order tools, system, messages; 1.25x for 5-minute writes; the 512-token minimum cacheable prefix on the 5.5 models (stated, read 2026-11-03).
- LiteLLM 1.96.2's Anthropic usage: `prompt_tokens` holds `input_tokens` plus cache reads and writes (`litellm/llms/anthropic/chat/transformation.py`, `calculate_usage`), which `spend.usage_of` takes apart (read 2026-11-03).
