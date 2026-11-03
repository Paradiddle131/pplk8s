# The semantic agent bet

A parallel research track ([Map #324](../../../../../issues/324), branch `claude/semantic-bet`, profile [`docs/agents/autopilot-semantic-bet.md`](../../agents/autopilot-semantic-bet.md), `semantic/PLAN.md` SL-25).
It measures, on the Compose lab and on the real lab project, what Google's native stack now covers for "an agent that answers through a semantic layer", and ends in one report with a verdict on what is worth building from here.

## Why it exists

- The owner's working assumption was "a GCP-native data agent lacks a semantic layer"; Knowledge Catalog now ingests dbt MetricFlow (GA 2026-09-24) and Google says it grounds Conversational Analytics and custom agents (2026-10-29), so the assumption has to be seen in action, not argued.
- Desk research, three grilling rounds and a cold review (2026-11-02, [the starting point](findings/2026-11-02-324-starting-point.md)) concluded: don't build a platform; outside Looker nothing on GCP binds an agent to a dbt semantic layer, it can only shape or ground what the agent reads; whether that is enough is measurable.
- Owner facts (2026-11-02): work runs dbt and MetricFlow, has no Looker (out of scope here too), and its data agents' graph sources are unknown.

## The question register

Each wake changes only its own rows: status (`open`, `measuring`, `answered`, `still unknown`) and the finding that answers it.

| # | Question | Issue | Status | Finding |
|---|---|---|---|---|
| Q1 | What does Knowledge Catalog store when it imports our dbt MetricFlow project, and what can an agent read back (`lookup_context`)? | #326 | answered (trimmed manifest; `compile_query` advertised, fails in the backend for any request) | [2026-11-03](findings/2026-11-03-326-kc-dbt-import.md), [the query tools](findings/2026-11-03-349-kc-compile.md) |
| Q2 | Does a BigQuery data agent use the imported metric definitions, compared with no context and with our generated context? | #327 | answered (no: never named or applied; six traps, three runs) | [2026-11-03](findings/2026-11-03-327-kc-data-agent.md) |
| Q3 | Can an ADK agent built only on Google's managed MCP servers (Knowledge Catalog, BigQuery) answer through the metrics? | #328, #346, #349, #350 | answered (yes; with only `silver` in reach, 11 of 12 on one run) | [offline part](findings/2026-11-03-346-mcp-offline.md), [live](findings/2026-11-03-328-mcp-live.md), [the query tools](findings/2026-11-03-349-kc-compile.md), [silver only](findings/2026-11-03-350-mcp-silver.md) |
| Q4 | Do governed views, table functions and parameterised verified queries make a data agent use the defined metrics; does `bqRoutines` take a table function? | #329 | answered (shapes; rates are #333's) | [offline and live](findings/2026-11-03-329-bet-shaped.md) |
| Q5 | How far can generated MCP Toolbox tools over those table functions go, and what falls outside their shapes? | #330, #344 | answered (right inside their shapes, mostly declined outside; two confident-wrong traps; rates are #333's) | [offline part](findings/2026-11-03-344-toolbox-shapes.md), [live](findings/2026-11-03-330-toolbox-live.md) |
| Q6 | Which metrics compile to graph measures, and does a data agent aggregate through them when it has the graph beside the tables? | #331 | answered (shapes; rates are #333's) | [offline and live](findings/2026-11-03-331-graph-measures.md) |
| Q7 | Do row policies hold through views, table functions and authorized routines; does conversation logging keep row-scoped answers read through a view? | #332, #345 | answered (row policies hold on every path); logging still unknown | [offline part](findings/2026-11-03-345-rls-offline.md), [live](findings/2026-11-03-332-rls-live.md) |
| Q8 | On a frozen question set, which path gives the right number, and which fails confidently? | #325, #340, #341, #333 | measuring | [the frozen set and rule](findings/2026-11-03-325-frozen-eval.md), [RULE.md](RULE.md), [its scoring](findings/2026-11-03-340-rule-scoring.md), [the local arms](findings/2026-11-03-341-local-arms.md) ([eval-local.md](eval-local.md)) |
| Q9 | What do Lightdash and dbt-mcp give a team on our project for free, and what is Enterprise or platform only? | #334 | answered | [dbt-mcp](findings/2026-11-03-334-dbt-mcp.md), [Lightdash](findings/2026-11-03-334-lightdash.md) |
| Q10 | What moved at Google, dbt and Apache Ossie while the track ran? | #335 | open | [watch](findings/watch.md) |
| Q11 | Verdict: what is worth building, where (a new repo or not), what not, and what transfers to work? | #336 | open | |

## The arms

Named and frozen by #325 before any is scored; each is built by its own issue.

| Arm | What answers | Built by |
|---|---|---|
| `native-context` | the data agent with our generated context (PR #310) | done |
| `native-governed` | the data agent over the governed tables (PR #310) | done |
| `native-kc` | the data agent grounded by Knowledge Catalog's import | #327 |
| `native-shaped` | the data agent with views, table functions and verified queries | #329 |
| `native-graph` | the data agent with a graph and its measures beside the tables | #331 |
| `native-mcp` | an ADK agent on Google's Knowledge Catalog and BigQuery MCP servers | #328 |
| `custom-metricflow` | the semantic agent's MetricFlow tools | done |
| `custom-toolbox` | generated MCP Toolbox tools over the table functions | #330 |
| `baseline` | text-to-SQL that reads the generated docs (#186) | #333 |

## Where things go

- `findings/<YYYY-MM-DD>-<issue>-<slug>.md`: one per issue (the profile's § Recording); [`findings/watch.md`](findings/watch.md): the daily watch.
- `probes/`: the scripts a finding ran, each with a docstring saying how to run it.
- `RULE.md` (#325), `eval.md` (#333), `REPORT.md` (#336).

## Pages from 2026-11-02

- [The semantic agent bet](https://claude.ai/artifact/3WrtWZPt92C7Mdt8bNhuuw): the first verdict, before measurement.
- [One chat, two repos](https://claude.ai/artifact/WFGLtAD9gruaVCixvLQtyu): where the chat and the semantic layer should live.
- The roadmap of this track: an artifact on Map #324.
