# The Claude Code MetricFlow setups' filtered queries all failed (#432)

Written 2026-11-09T11:50Z; part of the fairness epic #424 (#425).

## The question

One strict Sonnet run (`cc-metricflow-compute`, `hard_cpa_search_september` run 2, hard-v2) said "the semantic layer's query tool failed every time I called it" and was scored declined: was that the setup or an infrastructure fault?

## What was observed (measured)

- The run's stream (`cc-strict/streams/cc-metricflow-compute/sonnet/hard-v2/hard_cpa_search_september-r2.jsonl.gz`, as logged on 2026-11-06; git history keeps it): three `query_metrics` calls, each with a `campaign__channel` filter, each answered `Error executing tool query_metrics`.
- The same query called directly (`semantic_agent.tools.query_metrics`) returns rows; called through the MCP server's wrapper (`mcp_server.served`) it raises `TypeError: Object of type Filter is not JSON serializable`: MCP validates `filters` into `Filter` models, and the audit row's `jsonb` write could not hold them, so every filtered call failed its audit write and was withheld. ADK setups pass plain dicts and never met it.
- The search of every strict stream (3,246): 1,133 tool errors `Error executing tool`, every one on a `query_metrics` call with `filters`, none without; they touch 446 recorded runs: `cc-metricflow` and `cc-metricflow-compute`, Haiku 207, Sonnet 212, Opus 27 (by setup, model and set in the script's census). `cc-native-mcp` (another server) has none.
- No identical filtered query succeeded anywhere before the fix (223 distinct failing argument sets, 0 of them ever answered).

## What was done

- The fix: `mcp_server.served` hands the audit the arguments as JSON (`pydantic_core.to_jsonable_python`), test `test_a_filtered_query_is_audited_with_its_filters_as_json`; the same filtered query through the fixed server returns rows and writes its audit row.
- The 446 runs are a faulty setup, so redacted as test faults (`redacted.jsonl` `run` rows, issue 432), their recorded answers marked stale (`cc-strict/stale.jsonl`, by SHA-256; the answers files are never edited), with `387_cc_strict.py filter-faults`.
- The 419 Haiku and Sonnet runs were asked again through the strict runner on the fixed server (a smoke case first, read), scored with `328_mcp_live.py --agent 387_cc_strict.py`, and judged by Haiku; the 27 Opus runs are not asked again without the owner's go (#452).
- On the way: `387_cc_strict._parts` read `cc-metricflow-compute-*` answers files as setup `cc-metricflow` with model `compute`; it now matches the longest setup name first (its `redact` check then still finds no tool fault).

The spoiled runs against their reruns (right and confident-wrong runs):

| Set | Setup | Model | Runs | Right before | Right after | Confident-wrong before | Confident-wrong after |
|---|---|---|---|---|---|---|---|
| frozen | cc-metricflow | haiku | 31 | 28 | 31 | 2 | 0 |
| frozen | cc-metricflow | sonnet | 35 | 22 | 32 | 6 | 0 |
| frozen | cc-metricflow-compute | haiku | 31 | 28 | 31 | 3 | 0 |
| frozen | cc-metricflow-compute | sonnet | 38 | 31 | 38 | 0 | 0 |
| hard | cc-metricflow | haiku | 29 | 22 | 29 | 3 | 0 |
| hard | cc-metricflow | sonnet | 28 | 17 | 24 | 0 | 0 |
| hard | cc-metricflow-compute | haiku | 31 | 30 | 30 | 0 | 1 |
| hard | cc-metricflow-compute | sonnet | 33 | 28 | 31 | 0 | 0 |
| hard-v2 | cc-metricflow | haiku | 44 | 31 | 37 | 5 | 5 |
| hard-v2 | cc-metricflow | sonnet | 35 | 21 | 33 | 1 | 0 |
| hard-v2 | cc-metricflow-compute | haiku | 41 | 36 | 35 | 3 | 4 |
| hard-v2 | cc-metricflow-compute | sonnet | 43 | 33 | 38 | 4 | 4 |

In all: 419 runs, right 327 before and 389 after, confident-wrong 27 before and 14 after.

## What it means

- The Claude Code MetricFlow rows were scored on a broken server for every question that needs a filter (a country, a channel, a cohort); their models often worked around it (327 of 419 runs were still right), and where they could not, the fault scored as the setup's own decline or guess.
- With the fix, those rows gain about 15 points on the touched runs; they stay descriptive (RULE.md: outside § The rule's decision), and their Opus rows keep 27 redacted runs until the owner says go.
- The main track's MCP server (the deployed semantic agent's) had the same fault for any MCP client that filters; it is fixed there too.

## Opus, asked again (2026-11-09T14:35Z-14:51Z)

The owner said go for the 27 Opus runs, 2026-11-09, in a session.
A smoke case through the fixed server first (`cc-metricflow`, `hard_cpa_search_september`): its filtered `query_metrics` call returned a row, €124.84 per booking, with a clean audit.

The 27 spoiled runs against their reruns (logged outcomes before, scored and judged by Haiku after; the redacted runs were never judged, so their unclear turns stay unclear):

| Set | Setup | Model | Runs | Right before | Right after | Confident-wrong before | Confident-wrong after | Unclear before |
|---|---|---|---|---|---|---|---|---|
| hard-v2 | cc-metricflow | opus | 13 | 6 | 7 | 0 | 0 | 1 |
| hard-v2 | cc-metricflow-compute | opus | 14 | 10 | 14 | 1 | 0 | 2 |

In all: 27 runs, right 16 before and 21 after, confident-wrong 1 before and 0 after.

**The pass asked more than the go covered.**
`387_cc_strict.py run <setup> opus hard-v2 --runs 3` fills every case up to three runs, not only the stale ones: it asked 126 `cc-metricflow` and 127 `cc-metricflow-compute` runs, 253 in all, 226 of them beyond the 27 approved (about $27.58 of `claude -p` subscription usage as the streams report it; no API billing).
The runner printed its count before asking; the session read only the pass's last lines.
The 226 runs are valid strict runs on the fixed server and are kept in the logs and judged, but the scores and pages were not rebuilt with them: whether they count is the owner's decision (#432, #452).
`387_cc_strict.py` now refuses an Opus pass without `--limit`, and one that would ask more than it (`over_budget`, `test_an_opus_pass_names_its_size_and_never_asks_more`).

**Kept** (owner, 2026-11-09, in a session: "#432 can keep as recommended"): the 226 runs count, so hard-v2's two MetricFlow setups have a whole strict Opus row at k = 3; `results.json` and the pages are rebuilt with them.

## What stays unknown

- The earlier subagent `claude-code (...)` rows used the same server; their transcripts are self-reported, so the fault cannot be counted there; they leave the page once strict rows replace them (#452).
