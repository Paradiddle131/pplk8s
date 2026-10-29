# dbt semantic layer without dbt Cloud: spike and design facts

Research for [#99](https://github.com/Paradiddle131/pplk8s/issues/99) (Map: dbt semantic layer and a metrics agent), run on 2026-10-29 (UTC) in a cloud session against the Compose warehouse.
"Measured" means run here; "stated" means read from the linked page; "unverified" means neither.

S1 to S3 absorbed the spike's semantic YAML, pins, results, the authored-context schema and the agent pins into `dbt/` and `services/semantic-agent/`; what is left here, the native patterns and the unverified points, goes with S5.

## Verdict

The semantic layer runs entirely on open-source dbt: the YAML spec is parsed by `dbt-core`, and the `dbt-metricflow` CLI and Python API validate and query it against Postgres with no dbt Cloud account (measured).
Only the hosted Semantic Layer API, its MCP tools and dbt Cloud discovery are closed (stated: the `dbt-mcp` semantic-layer tools need platform credentials).
A derived metric defined once in YAML reproduces the hand-written `exposed.net_sales_daily` to the cent (measured; `make semantic-check` holds it now).

## Native patterns (stated, Google docs 2026-10)

The Conversational Analytics API's [integration patterns](https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/integration-patterns) page names ten; the ones that shape the lab:

| Pattern | What runs | Lab stand-in |
|---|---|---|
| 6 ADK schema-driven | `BigQueryToolset.ask_data_insights` with inline table references; SQL from schema inference, no semantic guardrails | the eval baseline: an ADK agent with one `execute_sql` tool over gold and exposed |
| 7 ADK governed | `DataAgentToolset.ask_data_agent` on a pre-configured data agent (knowledge sources, descriptions, instructions, verified queries, glossary) | the semantic agent: the same ADK agent with a MetricFlow-backed toolset in the data agent's place |
| 9 MCP | MCP Toolbox `bigquery-conversational-analytics` wrapping `chat`; ADK connects through `McpToolset` | not built; the ADK toolset seam covers it |

[BigQuery data agents](https://docs.cloud.google.com/bigquery/docs/conversational-analytics) take custom table and field metadata, instructions, verified queries (formerly golden queries) and glossary terms (BigQuery custom glossary or Knowledge Catalog), in that priority; they advise curated views over agent-chosen joins, at most 100 knowledge sources and about 20 per agent in practice.
The authored context's `system_instruction` YAML ([page](https://docs.cloud.google.com/gemini/docs/conversational-analytics-api/data-agent-authored-context-bq)) is generated and checked by `dbt/scripts/build_catalog.py` and `check_catalog.py` (S2); for S5's mapping, table and column `description`, `synonyms` and `tags` are structured fields set beside it (the generator leaves descriptions to `persist_docs`, which writes BigQuery descriptions), and `stagingContext` and `publishedContext` version it.
`DataAgentToolset` ([ADK docs](https://adk-labs.github.io/adk-docs/integrations/data-agent), ADK ≥ 1.23) exposes `list_accessible_data_agents`, `get_data_agent_info` and `ask_data_agent`, takes a `DataAgentCredentialsConfig` and a `DataAgentToolConfig` (`location`, `max_query_result_rows`), and references the agent as `projects/{project}/locations/{location}/dataAgents/{agent}`.

What this means for the design: every input of a native data agent (descriptions, relationships, glossary, verified queries) can be generated from the dbt manifests, so the semantic YAML is the single source and the native agent's context is a build artefact, not hand-written text.

## Unverified

- `dbt compile` on a `dbt-bigquery` target without a warehouse (S5 settles it; `dbt parse` works offline for certain).
- The exact `ask_data_agent` tool arguments (the ADK page does not list them); the lab toolset's contract is `question` in, text plus rows plus SQL out, which is what the docs describe.
