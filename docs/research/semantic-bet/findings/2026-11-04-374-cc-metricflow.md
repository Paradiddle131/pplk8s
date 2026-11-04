# The same MetricFlow tools through a Claude Code subagent: the harness sanity check (#374)

Question: does the model behind the agent answer differently when it is a Claude Code subagent on the subscription instead of ADK on the Anthropic API, on the same tools, rules and questions? The owner asked to keep this as metadata and a sanity check, not as a report headline (2026-11-04).

## What was run

- `semantic_agent.tool_cli` exposes the three MetricFlow tools as a command line, each data call audited as the ADK agent's is; `probes/374_cc_prompt.md` gives the subagent the ADK agent's rules nearly word for word (`toolset_metricflow.INSTRUCTION`); `probes/374_cc_agent.py --batches` gives it ids and questions only.
- 2026-11-04, 19:2xZ to 19:40Z: 12 Haiku subagents (Agent tool, `model: haiku`), one batch of 10 to 12 cases each, run 1 of both sets (96 + 43 cases); answers in `374-cc-answers/haiku-*.jsonl`, scored by `328_mcp_live.py --agent 374_cc_agent.py --no-canary` into `eval[-hard]-cc-metricflow.jsonl`; `results.json` rows carry `"harness": "claude-code-subagent"`.
- A first batch found two wrapper faults, fixed before the rest: a tool exception printed nothing (now returned as `{"error": ...}`), and answers were matched to cases by their first question, which conversation cases share (now by every question).

## What was observed (`measured`, results.json at 2026-11-04T19:39Z; the subagent at k = 1, the API at k = 3)

| Haiku on the MetricFlow tools | Frozen: right | Frozen: confident-wrong | Frozen `uncovered` right | Hard: right | Hard: confident-wrong |
|---|---|---|---|---|---|
| ADK, Anthropic API (`custom-metricflow`) | 81.2% [73.3, 88.5] | 2.4% | 44% | 73.6% [61.2, 85.3] | 9.3% |
| Claude Code subagent (`cc-metricflow`) | 66.7% [56.2, 76.0] | 5.2% | 7% | 44.2% [30.2, 58.1] | 18.6% |

- The harness changes the result: lower accuracy on both sets (intervals apart on the hard set), mostly where no metric covers the question (frozen `uncovered` 7% against 44%) and through more confident-wrong numbers on the hard set.

## Likely causes (`stated` by the subagents' own reports, not yet measured one by one)

- One session per batch: the subagents ran `list_metrics` once and carried it across 10 to 12 cases, where RULE.md and the API runs use a fresh session per run.
- Tool friction answered by improvising: a filter error answered by dropping the filter (`hard_turkish_vs_dutch_per_order`), a figure computed by hand against the rules (`followup_how_computed`, "EUR 17.50"), a windowed `customers_to_date` worked around by a month grouping.
- A stricter reading of "if no metric answers, say so": the API agent answers some `uncovered` cases by composing metrics; the subagents mostly declined.
- Isolation is by instruction only; one subagent made an unrelated read-only scheduled-task listing call it reported itself.

## What it means for the verdict

- None for the rule: `cc-metricflow` is descriptive (RULE.md § Changes since freezing, 2026-11-04). It says the numbers in this bet belong to the agent harness as much as to the model, so the report compares setups within one harness.
- As metadata: every row says what ran it (`harness`), so a reader of the data can tell an API run from a subagent run.

## Still unknown

- Runs 2 and 3 of the subagent, and Sonnet and Opus as subagents.
- Which cause above weighs most (a fresh subagent per case would separate the session effect).
