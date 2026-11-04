# The same MetricFlow tools through a Claude Code subagent: the harness sanity check (#374)

Question: does the model behind the agent answer differently when it is a Claude Code subagent on the subscription instead of ADK on the Anthropic API, on the same tools, rules and questions? The owner asked to keep this as metadata and a sanity check, not as a report headline (2026-11-04).

## What was run

- `semantic_agent.tool_cli` exposes the three MetricFlow tools as a command line, each data call audited as the ADK agent's is; `probes/374_cc_prompt.md` gives the subagent the ADK agent's rules nearly word for word (`toolset_metricflow.INSTRUCTION`); `probes/374_cc_agent.py --batches` gives it ids and questions only.
- 2026-11-04, 19:2xZ to 19:40Z: 12 Haiku subagents (Agent tool, `model: haiku`), one batch of 10 to 12 cases each, run 1 of both sets (96 + 43 cases); answers in `374-cc-answers/haiku-*.jsonl`, scored by `328_mcp_live.py --agent 374_cc_agent.py --no-canary` into `eval[-hard]-cc-metricflow.jsonl`; `results.json` rows carry `"harness": "claude-code-subagent"`.
- A first batch found two wrapper faults, fixed before the rest: a tool exception printed nothing (now returned as `{"error": ...}`), and answers were matched to cases by their first question, which conversation cases share (now by every question).

## What was observed (`measured`, results.json at 2026-11-04T19:39Z; the subagent at k = 1, the API at k = 3)

| On the MetricFlow tools (first two rows Haiku) | Frozen: right | Frozen: confident-wrong | Frozen `uncovered` right | Hard: right | Hard: confident-wrong |
|---|---|---|---|---|---|
| ADK, Anthropic API (`custom-metricflow`) | 81.2% [73.3, 88.5] | 2.4% | 44% | 73.6% [61.2, 85.3] | 9.3% |
| Claude Code subagent (`cc-metricflow`) | 66.7% [56.2, 76.0] | 5.2% | 7% | 44.2% [30.2, 58.1] | 18.6% |
| Sonnet: ADK, Anthropic API | 74.7% [66.0, 82.6] | 1.4% | 18% | 57.4% [41.9, 72.1] | 5.4% |
| Sonnet: Claude Code subagent | 70.8% [61.5, 79.2] | 1.0% | 3% | 51.2% [37.2, 65.1] | 30.2% |

- Sonnet (12 subagents, 19:3xZ to 19:47Z, about 100k tokens a batch): on the frozen set the two harnesses tie within their intervals (accuracy and confident-wrong both), while on the hard set the subagent is confidently wrong in 30.2% of cases against 5.4% through the API; so the harness effect is not one direction for every model, but on the hard set both models' subagents are more often confidently wrong.
- The harness changes the result: lower accuracy on both sets (intervals apart on the hard set), mostly where no metric covers the question (frozen `uncovered` 7% against 44%) and through more confident-wrong numbers on the hard set.

## The session effect, measured (owner, 2026-11-04: "it sounds like you did a bad job trying to give both cases the same environment")

The first pass put about 12 cases in one subagent session, where every API run starts fresh; so Haiku's hard set was rerun with one fresh subagent per case (43 subagents, about 90k tokens each, mostly Claude Code's own prompt and `list_metrics`), logged as `claude-code (fresh-haiku)` with `"session": "fresh per case"`:

| Haiku, hard set, run 1 | Right | Confident-wrong | `covered` right | `uncovered` right |
|---|---|---|---|---|
| ADK, Anthropic API (fresh per run, k = 3) | 73.6% [61.2, 85.3] | 9.3% | 88% | 56% |
| Claude Code subagent, shared per batch | 44.2% [30.2, 58.1] | 18.6% | 79% | 0% |
| Claude Code subagent, fresh per case | 58.1% [44.2, 72.1] | 4.7% [0.0, 11.6] | 92% | 16% |

- The shared session caused most of the confident-wrong gap: fresh subagents are confidently wrong less often than the API agent; the batched pass's numbers are kept and labelled, never used as the harness comparison.
- What remains is the harness: the subagent declines far more of the questions no metric covers (16% against 56% right), so its accuracy stays lower, with intervals that now overlap the API's.
- Still different even per case: Claude Code's own system prompt and shell-called tools against ADK's function calling, the rules as a task message rather than a system instruction, isolation by instruction (one fresh subagent tried an unrelated `create_session` call, refused by the session's classifier, nothing created).

## Sonnet and Opus, fresh per case (owner's go, 2026-11-04, about 20:15Z)

- 2026-11-04, 20:16Z to 20:39Z: one fresh subagent per hard case for Sonnet (43, `model: sonnet`) and Opus (43, `model: opus`), at most 20 at once, each told by `probes/374_cc_prompt.md` rendered per case (`BET_CC_MODEL=fresh-<model>`, `BET_CC_SESSION=fresh-<model>-hard-run1-NN`) and handed a one-line pointer to that rendered file (whether Haiku's fresh run got the prompt inline or the same way is not recorded); one test case per model was read before the rest (both right, matching Haiku's answer to `hard_aov_last_month`).
- About 77k to 83k subagent tokens a case (Claude Code's own prompt and `list_metrics` dominate): about 3.4M for each model on the subscription, no API credits.
- Several subagents reported their own slips: hand-computed differences (Sonnet, `hard_social_vs_search_lead_gap`), an extra `cat` or `python3` pipe beside the tool, a `calls` list that missed one call; scored as given, since an agent's slips are part of what it answers.

| Hard set, run 1, Claude Code subagent fresh per case (`measured`, results.json at this commit) | Right | Confident-wrong | `covered` right | `uncovered` right |
|---|---|---|---|---|
| Haiku | 58.1% [44.2, 72.1] | 4.7% [0.0, 11.6] | 92% | 16% |
| Sonnet | 48.8% [34.9, 62.8] | 11.6% [2.3, 20.9] | 83% | 5% |
| Opus | 51.2% [37.2, 65.1] | 9.3% [2.3, 18.6] | 83% | 11% |
| (Sonnet, ADK on the API, k = 3) | 57.4% [41.9, 72.1] | 5.4% [0.0, 12.4] | 83% | 25% |

- Fresh sessions bring Sonnet's and Opus's confident-wrong down from their batched 30.2% and 25.6% to 11.6% and 9.3%: the shared session was the larger part of the gap for every model.
- The three models tie within their intervals as subagents; the larger model does not decline less on `uncovered` questions, so the harness's decline habit, not the model, sets that column.
- Sonnet as a fresh subagent against Sonnet through ADK: intervals overlap on both columns; the subagent declines more `uncovered` questions (5% against 25%).

## Likely causes (`stated` by the subagents' own reports, not yet measured one by one)

- One session per batch: the subagents ran `list_metrics` once and carried it across 10 to 12 cases, where RULE.md and the API runs use a fresh session per run.
- Tool friction answered by improvising: a filter error answered by dropping the filter (`hard_turkish_vs_dutch_per_order`), a figure computed by hand against the rules (`followup_how_computed`, "EUR 17.50"), a windowed `customers_to_date` worked around by a month grouping.
- A stricter reading of "if no metric answers, say so": the API agent answers some `uncovered` cases by composing metrics; the subagents mostly declined.
- Isolation is by instruction only; one subagent made an unrelated read-only scheduled-task listing call it reported itself.

## What it means for the verdict

- None for the rule: `cc-metricflow` is descriptive (RULE.md § Changes since freezing, 2026-11-04). It says the numbers in this bet belong to the agent harness as much as to the model, so the report compares setups within one harness.
- As metadata: every row says what ran it (`harness`), so a reader of the data can tell an API run from a subagent run.

## Still unknown

- Runs 2 and 3 of the fresh subagents, and the frozen set fresh per case.
- Which of the remaining harness causes (system prompt, shell tools, the rules as a task message) weighs most.
