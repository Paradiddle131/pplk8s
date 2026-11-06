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

## The frozen set, fresh per case (owner's go for Haiku and Sonnet, and about 20 Opus runs a setup, 2026-11-04T23:13Z)

- 2026-11-04, 23:11Z to 23:48Z: one fresh subagent per frozen case, run 1: Haiku on all 96, Sonnet on all 96, Opus on 20 cases sampled across the groups in proportion (2 `trap`, 9 `covered`, 6 `uncovered`, 1 `distractor`, 1 `conversation`, 1 `planted`: case numbers 1, 2, 6, 11, 16, 21, 27, 29, 31, 34, 40, 45, 50, 57, 63, 72, 77, 82, 87, 92); one test case per model read before the rest (both right).
- Prompts rendered per case by `374_cc_agent.py --batches frozen 1 1 DIR fresh-<model>` then `--render DIR ANSWERS fresh-<model>` (new in this pass); the subagent is handed one line: read the rendered prompt and follow it, using only Read and Bash.
- About 68k to 83k subagent tokens a case on the subscription, no API credits; the token count fell by about 5k from Haiku's case 46 on, when the session's deny rules (below) shrank the subagents' tool list.
- Isolation by instruction leaked tool calls outside the task: Haiku made a remote-session listing call (case 25), an `interrupt_session` on "self" (case 33, refused, no effect) and read-only documentation and session lookups (cases 38, 55, 57, 64, 66, 96); from case 35 the one-line brief names the two allowed tools, and the session denies the remote-session tools by permission rule, so Sonnet's and Opus's cases made no such call. None touched an answer; a tool-restricted agent type (Bash and Read only) is the cleaner harness for the next pass.
- A container restart at about 23:30Z cut a Sonnet wave; the answers already written were kept, and the two cases it missed (16, 17) were asked again in a fresh subagent.
- Scorer fix: the subagent scorer took a case's recorded answers in run order, so an answer already logged as run 1 would have been scored again as run 2; a logged (case, run) now stays out of the queue.

| Frozen set, run 1, Claude Code subagent fresh per case (`measured`, results.json at this commit) | Right | Confident-wrong | `covered` right | `uncovered` right |
|---|---|---|---|---|
| Haiku (96 cases) | 72.9% [63.5, 81.2] | 3.1% [0.0, 7.3] | 97% | 17% |
| Sonnet (96 cases) | 74.0% [64.6, 82.3] | 3.1% [0.0, 7.3] | 99% | 17% |
| Opus (20 of 96 cases) | 70.0% [50.0, 90.0] | 0.0% | 100% (14) | 0% (6) |
| (Haiku, shared session per batch) | 66.7% [56.2, 76.0] | 5.2% | | 7% |
| (Haiku, ADK on the API, k = 3) | 81.2% [73.3, 88.5] | 2.4% | | 44% |
| (Sonnet, ADK on the API, k = 3) | 74.7% [66.0, 82.6] | 1.4% | | 18% |

- On the frozen set the fresh subagents answer nearly every covered question right (97 to 100%) and decline most uncovered ones (0 to 17% right), the same shape as the hard set; the three models tie within their intervals.
- Sonnet as a fresh subagent ties Sonnet through ADK on both columns (74.0% against 74.7%; 17% against 18% on `uncovered`); Haiku as a fresh subagent stays below Haiku through ADK on `uncovered` (17% against 44%), so the harness gap is Haiku's, not every model's.
- Fresh sessions bring Haiku's frozen confident-wrong from 5.2% (batched) to 3.1%, as they did on the hard set.

### Still unknown

- Runs 2 and 3 of the fresh subagents on both sets; Opus on the other 76 frozen cases (the owner's go is needed past about 20 Opus runs a setup).

## Haiku and Sonnet at the rule's k, fresh per case (2026-11-05, to 01:14Z)

- Runs 2 and 3 of both sets for Haiku and Sonnet, one fresh subagent per case-run, about 10 at once, the brief and the rendered prompt as in run 1 (the two-tool brief from Haiku's frozen case 35 of run 1 on), answers pushed after every wave; the hard set's runs 2 and 3 ran before the frozen set's.
- No stray remote-session call in runs 2 and 3: the deny rules held, and every subagent reported only the tool command and the answer file.
- A few reported their own recoveries and were scored as given: an empty argument to `list_metrics` retried with none, a numeric filter value retried as a string, a two-value filter retried as a grouping, an end date past the layer's limit retried within it.
- Opus stays at its sample (20 frozen cases, run 1; 43 hard cases, run 1, from before the owner's go): its 20 frozen runs are the owner's limit for that setup.

| Claude Code subagent fresh per case, k = 3 (`measured`, results.json at this commit) | Frozen: right | Frozen: confident-wrong | Frozen `uncovered` right | Hard: right | Hard: confident-wrong | Hard `uncovered` right |
|---|---|---|---|---|---|---|
| Haiku | 72.6% [63.5, 80.6] | 4.5% [1.7, 8.0] | 17% | 54.3% [40.3, 68.2] | 7.0% [1.6, 13.2] | 14% |
| Sonnet | 72.9% [63.9, 81.2] | 2.1% [0.3, 4.2] | 16% | 50.4% [35.7, 65.1] | 12.4% [4.7, 21.7] | 9% |
| Opus (run 1 only: 20 frozen, 43 hard cases) | 70.0% [50.0, 90.0] | 0.0% | 0% | 51.2% [37.2, 65.1] | 7.0% [0.0, 16.3] | 11% |
| (Haiku, ADK on the API, k = 3) | 81.2% [73.3, 88.5] | 2.4% [0.7, 4.5] | 44% | 73.6% [61.2, 85.3] | 9.3% [2.3, 17.8] | 56% |
| (Sonnet, ADK on the API, k = 3) | 74.7% [66.0, 82.6] | 1.4% [0.0, 3.5] | 18% | 57.4% [41.9, 72.1] | 5.4% [0.0, 12.4] | 25% |

- Run by run the rates hold still: Haiku frozen 72.9%, 74.0%, 70.8% right; Sonnet frozen 74.0%, 72.9%, 71.9%; Haiku hard 58.1%, 51.2%, 53.5%; Sonnet hard 48.8%, 48.8%, 53.5%. Run 1 was not a lucky draw.
- Confident-wrong drifts up across runs for Haiku (frozen 3.1%, 4.2%, 6.2%; hard 4.7%, 7.0%, 9.3%) and for Sonnet on the hard set (11.6%, 11.6%, 14.0%); the same cases recur (`bet_sessions_per_order` was confident-wrong in run 3 for both models), so it reads as noise on a few hard cases, not a trend; k = 3 is the figure to quote.
- At k = 3 Sonnet as a subagent still ties Sonnet through ADK on the frozen set (72.9% against 74.7%) and stays inside its interval on the hard set (50.4% against 57.4%), but its hard confident-wrong is about twice ADK's (12.4% against 5.4%, intervals overlapping).
- Haiku as a subagent stays below Haiku through ADK on both sets (72.6% against 81.2%; 54.3% against 73.6%), almost all of it in `uncovered` (17% against 44%; 14% against 56%): the harness gap is Haiku's, and it is the decline habit.
- Opus's hard confident-wrong reads 7.0% in results.json against 9.3% in run 1's table above: one of its four confident-wrong answers is now `unclear` to the scorer; the run-1 figure is kept above as it was measured.

### Still unknown

- Opus past its sample (needs the owner's go).
- Whether the decline habit is the harness's system prompt or its shell-tool framing (a Bash-and-Read-only agent type, `bet-subject`, now exists for that pass).

## The decline habit is not the general-purpose agent's prompt (Haiku, Bash-and-Read-only agent type, 2026-11-05, 01:17Z to 01:28Z)

- Question: Haiku as a fresh subagent declines most `uncovered` questions (17% right against 44% through ADK); does Claude Code's general-purpose agent prompt cause it?
- Haiku re-ran the frozen set once, one fresh subagent per case, as a custom agent type `bet-subject` (its definition copied to `probes/374_bet_subject_agent.md`): tools Bash and Read only, a two-line system prompt in place of the general-purpose agent's, the same rendered task prompt (`probes/374_cc_prompt.md`), handed only the prompt's path; label `claude-code (subject-haiku)`, scored at k = 1 like run 1 of the others.
- About 27k to 35k subagent tokens a case, against about 60k as a general-purpose subagent: the general-purpose prompt and tool list are about half of each case's tokens.
- No call outside the task; one subagent read its answers file back with `python3` to check the JSON, and reported it.

| Frozen set, Haiku, fresh per case (`measured`, results.json at this commit) | Right | Confident-wrong | `covered` right | `uncovered` right |
|---|---|---|---|---|
| Bash-and-Read-only agent type, k = 1 | 69.8% [60.4, 79.2] | 4.2% [1.0, 8.3] | 96% | 10% |
| General-purpose agent, run 1 | 72.9% [63.5, 81.2] | 3.1% [0.0, 7.3] | 97% | 17% |
| General-purpose agent, k = 3 | 72.6% [63.5, 80.6] | 4.5% [1.7, 8.0] | 97% | 17% |
| (ADK on the API, k = 3) | 81.2% [73.3, 88.5] | 2.4% [0.7, 4.5] | | 44% |

- The leaner agent type ties the general-purpose one (69.8% against 72.9% on the same run; 11 of 96 cases changed outcome, both ways) and declines `uncovered` questions as often or more (10% against 17%).
- So the gap to ADK is not the general-purpose agent's system prompt or its tool list. The task prompt's rules are the ADK agent's own (`374_cc_prompt.md` against `metrics.py` and `hybrid.py`: never compute a figure, say so when no metric answers, name the closest metrics), so the rules are not it either; what stays is Claude Code's base harness: tools reached as a shell command returning JSON text, not as typed function calls.

### Still unknown

- Whether typed function calls are what lets Haiku compose metrics for `uncovered` questions: the same three tools offered to a subagent as typed tools (an MCP server over `tool_cli`) would test it; not run, since it needs a new harness.

## Opus to 50 frozen cases (owner, 2026-11-05T19:50Z: "let's do 50 for now")

- 2026-11-05, 20:00Z to 20:03Z: 30 more fresh Opus subagents (`model: opus`, general-purpose, one per case), run 1, on frozen cases sampled so the 50 keep the set's group shares (`uncovered` 15, `covered` 23 by primary group, `trap` 6, `conversation` 4, `planted` 2, `distractor` 1): case numbers 3, 5, 9, 12, 15, 18, 22, 24, 25, 28, 30, 36, 39, 43, 46, 49, 51, 53, 55, 58, 60, 62, 71, 75, 78, 81, 84, 88, 90, 94; one test case read before the rest (right).
- The same one-line brief as before (Read and Bash only); the remote-session, GitHub, Docs and web tools were denied by a session permission rule for the waves, and no subagent reported a call outside the task. About 60k to 65k subagent tokens a case on the subscription, no API credits.
- One subagent met a filter error (`operator '=' takes exactly one value`) and retried with `!=`; the planted campaign names' instructions were ignored and reported as text.
- The hard set stays at run 1 (43 cases): 50 runs there would only add a second run on 7 cases.

| Frozen set, run 1, Claude Code subagent fresh per case (`measured`, results.json at this commit) | Right | Confident-wrong | `uncovered` right |
|---|---|---|---|
| Opus, 50 cases | 74.0% [62.0, 86.0] | 0.0% | 13% (2 of 15) |
| Haiku, the same 50 cases, run 1 | 37 of 50 right | | |
| Sonnet, the same 50 cases, run 1 | 39 of 50 right | | |

- Opus answers every `covered`, `trap`, `conversation`, `planted` and `distractor` case right (35 of 35 `covered`) and declines or misses 13 of 15 `uncovered` ones; the three models tie on the same cases, so the decline habit is the harness's, not the model's, now on 50 Opus cases instead of 20.
- Its five wrong answers are `uncovered` questions answered with the nearest metrics' raw figures instead of the asked ratio or gap (one subagent said so itself: the rules forbid computing the gap); none is confidently wrong.

## hard-v2's new cases (2026-11-06, 16:03Z to about 16:40Z)

- Why: `hard-v2` (RULE.md § Set versions, #375) carries v1's runs of its 41 unchanged cases into every setup, so each Claude Code setup needed only the 14 new cases (15 drafted, `hv2_first_order_value_october` retired by #382) for its hard-v2 row; #380 compares v1 and v2 per arm.
- Batches from `374_cc_agent.py --batches hard-v2 R 1 DIR fresh-<model>` (and size 20 for the batched setups), the retired case's batch dropped, then `--render`; the same one-line brief (read the rendered prompt, use only Read and Bash); one test case per model read before the rest (all three answered `hv2_net_revenue_on_september_orders` with the metric's figure and named its definition).
- Runs: Haiku and Sonnet fresh per case at k = 3 (42 subagents each), Opus fresh per case at k = 1 (14, within the owner's 50 a setup), and one batched session each for Haiku, Sonnet and Opus (14 cases, k = 1, as their v1 rows); at most 11 at once, the answers pushed after every wave; scored with `328_mcp_live.py --agent 374_cc_agent.py --set hard-v2 --no-canary`.
- No session deny rule held the remote-session and docs tools this time, unlike the 2026-11-05 waves: about a dozen Haiku subagents called the environment's read-only documentation tool once or twice, one Haiku subagent tried a remote `send_message` (refused by the session's classifier, nothing sent), and a few ran `cat`, `date` or `mkdir -p` beside the tool command; each reported it, none read a repository file or touched the answers of another case, and the answers are scored as given.

| hard-v2's 14 new cases (`measured`, results.json at this commit) | Right | Confident-wrong | New `composable` right | New `uncovered` right | All of hard-v2 right |
|---|---|---|---|---|---|
| Haiku, fresh per case, k = 3 | 23.8% [7.1, 42.9] | 21.4% [4.8, 40.5] | 33% | 0% | 45.5% |
| Sonnet, fresh per case, k = 3 | 7.1% [0.0, 21.4] | 23.8% [2.4, 45.2] | 0% | 0% | 37.0% |
| Opus, fresh per case, k = 1 | 7.1% [0.0, 21.4] | 14.3% [0.0, 35.7] | 0% | 0% | 38.2% |

- Pure MetricFlow through Claude Code answers none of the new `uncovered` cases on any model, as RULE.md's note written before any run expected ("pure MetricFlow should decline most of the `uncovered` group by design"); the subagents decline the medians and the unreturned-orders share every time and answer the rest with the nearest metric's figure.
- Confident-wrong rises on the new cases (14 to 24% against 7 to 12% on v1): almost all of it is two cases where the nearest metric gives a close but different number, `hv2_net_revenue_on_september_orders` (net revenue counts returns on their return date, 12,582.75 against the asked 12,547.75; 7 of 7 fresh runs) and `hv2_september_revenue_amsterdam_days` (UTC days against Amsterdam days; 6 of 7).
  Most of those answers name the difference ("not strictly September orders minus their own returns", "on UTC days, not the Amsterdam-day figure"), a hedge outside the scorer's list, so they wait for the blind judge (#366), which runs on the free quota with the lane's `backlog` step; the table above is before the judge.
- The batched rows are in `results.json`, labelled, and never used as the harness comparison (as on v1).
