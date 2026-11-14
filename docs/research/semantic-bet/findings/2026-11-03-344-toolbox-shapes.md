# Generated Toolbox tools over the seven table functions, and how much of the frozen set fits their shapes (#344)

Question (Q5, offline part): how far can generated MCP Toolbox tools over the `native-shaped` arm's table functions go, and what falls outside their shapes?
The live part (Toolbox against the lab project, an ADK agent on it, its answers) stays [#330](../../../../../../issues/330)'s, after [#329](../../../../../../issues/329)'s live part and the cost check ([#338](../../../../../../issues/338)).

## What was run

- 2026-11-03T04:40Z, offline: [`probes/330_toolbox_tools.py`](../probes/330_toolbox_tools.py) reads the seven `CREATE OR REPLACE TABLE FUNCTION bet_shaped.<name>(start_date DATE, end_date DATE)` in [`probes/329_bet_shaped.sql`](../probes/329_bet_shaped.sql) and writes [`probes/330_tools.yaml`](../probes/330_tools.yaml) in Toolbox's flat format: one `bigquery` source with `useClientOAuth: true`, one `bigquery-sql` tool per function (`SELECT * FROM bet_shaped.<name>(CAST(@start_date AS DATE), CAST(@end_date AS DATE))`, the function's description), one toolset `bet-shaped`; `--check` fails when the committed file is stale.
- 2026-11-03T04:41Z, offline: [`probes/330_toolbox_check.sh`](../probes/330_toolbox_check.sh) runs MCP Toolbox 1.1.0 (the release bucket's `v1.1.0/linux/amd64/toolbox`, created 2026-04-13, SHA-256 `17948e75…99ba29`) in a container with `--network none`, over MCP stdio: `initialize`, `tools/list`, then one `tools/call` with no token.
- 2026-11-03T04:43Z, offline: [`probes/330_shape_coverage.py`](../probes/330_shape_coverage.py) holds a verdict for each of the 96 frozen cases ([`semantic_bet.yaml`](../../../../services/semantic-agent/evals/semantic_bet.yaml)), read by hand from its question and expected SQL against the tools' columns: `exact` (one call, then a value, a sum of an additive column or a row picked), `derived` (the agent's own arithmetic over at most two calls: a ratio of sums, a growth, a share) or `out` (with what is missing).
  It counts the same for a counterfactual generator, one tool per metric returning it per day or over the whole range with no other dimension, computed from the cases' metrics and a hand list of the dimensions and filters each needs.

## What was observed (`measured`, the runs above)

- Toolbox 1.1.0 loads the generated file and starts with no credential and no network: `initialize` answers `Toolbox 1.1.0+binary.linux.amd64.da6f5f8`, protocol `2025-06-18`; `tools/list` serves the 7 tools, each with two required string parameters and the function's description (120 to 233 characters).
- The same file with a plain `bigquery` source (no `useClientOAuth`) does not start offline: `unable to initialize source "lab-bigquery": error creating client from ADC: … could not find default credentials`; with `useClientOAuth` the source builds no client until a call.
- A call over stdio is refused before any query: `{"code": -32600, "message": "missing access token in the 'Authorization' header"}`.
  A `useClientOAuth` source needs the HTTP transport, where the MCP client sends the user's token; stdio, which ADK's local toolsets often use, carries no header.
- Toolbox 1.x writes YAML as one document per object (`kind: source | tool | toolset`, `type: bigquery-sql`); `toolbox migrate` rewrites the 0.x `sources:`/`tools:` maps into it.
- What an agent sees per tool is a name, two dates and a description: not the output columns, not the SQL (Toolbox never serves a tool's statement).
- Coverage of the frozen set (the probe's output):

| Group | Cases | Saved-query tools: exact | derived | out | Per-metric tools: exact | derived | out |
|---|---|---|---|---|---|---|---|
| all | 96 | 26 | 12 | 58 | 46 | 2 | 48 |
| covered | 67 | 26 | 8 | 33 | 46 | 0 | 21 |
| uncovered | 29 | 0 | 4 | 25 | 0 | 2 | 27 |
| trap | 11 | 4 | 3 | 4 | 9 | 0 | 2 |
| distractor | 3 | 2 | 1 | 0 | 1 | 0 | 2 |
| conversation | 7 | 4 | 1 | 2 | 5 | 0 | 2 |
| planted | 4 | 0 | 0 | 4 | 0 | 0 | 4 |

- Why the seven tools miss 58 cases: no metric answers the question (24, the uncovered set's medians, percentiles, durations, weather), a metric the seven saved queries leave out (23: signups, the engagement, outreach, recruitment and call metrics, `return_rate`, `lead_to_booking_rate` …), a dimension they fix away (8: campaign, customer, signup month, net revenue by country, spend by day), a filter (1: order amount), the definition asked back (1), and one non-additive metric (`bet_customers_september`: `customers_distinct` comes per day, and the days do not add up to the month's distinct customers).
- The seven tools are used unevenly: `daily_sales` answers 20 of the 38 cases they reach, `channel_performance` 9, the other five 1 to 4 each.
- One tool per metric answers 19 cases the seven miss and loses 9 they reach (the ones needing country, channel, status, reason or a share by reason); the two generators together reach 57 of 96 cases (38 + 19), 53 of the 67 covered ones.

## What it means for the verdict

- Tools generated from saved queries are a thin front door: on this set they answer 26 of 96 cases exactly and 12 more only through the agent's own arithmetic, the place a governed definition was meant to remove.
  Per metric with dates only does better on covered cases (46 of 67) but drops every question that needs a dimension, so a shipping form that holds up needs dimensions and filters as parameters, which is a semantic-layer query API (MetricFlow's), not a list of SQL statements.
- Most uncovered cases fall to the agent either way (25 of 29 out with the seven tools, 27 per metric): a Toolbox-only arm is a decline-or-improvise arm on more than half the set, so #333 should score its declines, not only its right answers.
- `bet_customers_september` is a concrete trap for per-day tools: an agent that adds the days gets a confident wrong number from a governed tool.
- `useClientOAuth`, which work already uses, constrains the transport: the agent must reach Toolbox over HTTP with the user's token, so the eval's ADK agent cannot use a stdio toolset for this arm.

## Still unknown

- Whether BigQuery accepts the tools' statements (`CAST(@start_date AS DATE)` on a string parameter into a table function) and what the agent answers on the probe questions: live, #330, after #329's live part and #338.
- How an agent picks among seven tools whose descriptions name metrics loosely and never list columns; whether a richer generated description (columns, units, the grain) changes it.
- The verdicts are one reader's (this wake, 2026-11-03), written against the tools' columns, not run; the `derived` ones assume the agent does the arithmetic right.

## Sources

- MCP Toolbox's BigQuery source, `useClientOAuth`: <https://mcp-toolbox.dev/integrations/bigquery/source/> (`stated`, read 2026-11-03 through #330's notes); the 1.1.0 binary's `--help` and `migrate` (`measured`, 2026-11-03).
- The frozen set and its groups: [the #325 finding](2026-11-03-325-frozen-eval.md); the table functions: [the #329 finding](2026-11-03-329-bet-shaped.md).
