# The semantic layer on BigQuery

How each piece of the lab's semantic track maps to its work counterpart on GCP, and what the lab proves about getting there ([`semantic/PLAN.md`](../semantic/PLAN.md) R7, S5).
"Measured" means run in this repo (`make bigquery-check` and the checks it names); "measured (emulator)" means run on the BigQuery emulator by `make bigquery-emulator-check`; "stated" means read from Google's or dbt's documentation (2026-10); "unverified" means neither.

## What carries over unchanged

The dbt project, its semantic YAML and the catalog generator run on BigQuery's adapter with no edit (measured, `make bigquery-check`, offline):
- `dbt parse` and `mf validate-configs --skip-dw` pass on the compile-only `bigquery` target of `dbt/profiles.yml`.
- `dbt compile` of the semantic path (sales, returns, finance, semantic) passes, and all 16 compiled models parse as BigQuery SQL.
- `build_catalog.py` writes the agent catalog with `project.dataset.table` relations, and verified queries that read `` `pplk8s-lab`.`silver`.`orders` `` in BigQuery's dialect; `check_catalog.py` passes.

It also runs (measured (emulator), `make bigquery-emulator-check`, [`semantic/PLAN.md`](../semantic/PLAN.md) SL-7):
- `dbt build` of the semantic path, tests included, on the `bigquery_emulator` output: every model and test passes on GoogleSQL, as the emulator's ZetaSQL analyzer checks it.
- MetricFlow queries the eight metrics there, and they equal the hand-written gold and exposed tables the same build wrote, day by day.
- The emulator needs a shim for two gaps dbt-bigquery hits (`routines.list`, and DDL jobs reported as `SELECT`); real BigQuery has neither.

The target is compile-only: `method: oauth-secrets` with a placeholder token lets dbt build its client offline, and `--no-introspect --no-populate-cache` keeps compile from querying.
At work the same output takes `method: oauth` (application default credentials) and a real project.

## The mapping

| Lab piece | Work counterpart | How it gets there |
|---|---|---|
| Warehouse comments (`persist_docs` on gold and exposed) | BigQuery table and column descriptions, which Knowledge Catalog shows | The same dbt models with `persist_docs`; dbt-bigquery writes descriptions as it builds (stated) |
| Model contracts on gold and exposed (`contract: {enforced: true}`, a `data_type` on every column) | The BigQuery table schema, which Knowledge Catalog shows beside the descriptions | Contracts act at build time: dbt compares the model's columns with the contract before it builds, and dbt-bigquery creates a contracted table with the declared types (measured (emulator)); the schema and Knowledge Catalog are what agents read at query time. A view gets the name and type check but no constraints (stated) |
| `semantic.metrics` (one row per metric: name, label, description, type, models, pipelines) | Glossary terms: BigQuery custom glossary or Knowledge Catalog | The same model builds on BigQuery; the authored context's `glossaries` carry the same words |
| `semantic.glossary` (one row per business term that is not a metric: term, description, synonyms, metrics, dimensions) | The same glossary, for terms such as a cohort or a channel | `config.meta.glossary` on the dbt models; the same model builds on BigQuery, and the authored context's `glossaries` carry each term with its metrics and dimensions in the description (the documented glossary item has no field for them) |
| `target/catalog/data_agent/system_instruction.yaml` | The data agent's authored context: tables, fields and aggregations, relationships, glossary, additional descriptions | Generated from the manifests by `build_catalog.py` (S2); set as the agent's staging context, then published (`stagingContext`, `publishedContext`; stated) |
| `target/catalog/data_agent/example_queries.json` | The data agent's verified queries (formerly golden queries) | MetricFlow compiles each metric offline in the target's dialect (measured on BigQuery's) |
| `list_metrics`, `describe_metric`, `query_metrics` (MetricFlow) | `DataAgentToolset`: `list_accessible_data_agents`, `get_data_agent_info`, `ask_data_agent` (ADK ≥ 1.23; stated) | Swap the toolset in `semantic_agent/agent.py`; the agent, its instruction and its session store stay |
| `sql_baseline` (`execute_sql` over gold and exposed) | `BigQueryToolset.ask_data_insights` with inline table references | The "ADK schema-driven" pattern: what most teams run first, and what the eval scores against |
| `MODEL_BACKEND=openrouter` (free model) | `MODEL_BACKEND=gemini` | `model.py` is the only place naming a provider |
| ADK `DatabaseSessionService` on the metadata DB's `agent_sessions` | The same on Cloud SQL, or `VertexAiSessionService` | ADK's session URI |
| `agent_metrics` and `agent_sql` roles | IAM: dataset-level read on the datasets each agent may see (out of scope here) | Trust stays in the warehouse, not the prompt (SL-4) |
| Freshness from `ops.readiness` and `ops.product_deadlines` | The same two tables in BigQuery | The tool reads them; a native data agent needs them as a knowledge source or a verified query (unverified) |
| `validate_semantic_layer` in `finance_daily` | A Cloud Run Job on the dbt image whose command is `dbt parse && mf validate-configs` | Job overrides change args, not the command, so it is its own Job (unverified) |

What does not carry over: a native data agent does not run MetricFlow.
The metric definitions reach it as words and SQL: the glossary, the aggregations in the authored context, and one verified query per metric.
The lab's agent queries through MetricFlow itself, so its eval shows what the definitions are worth when they are enforced, not only described.

Scheduled queries and routines (stored procedures, UDFs, table functions) map onto dbt models, functions, macros and metrics as [`routines-and-scheduled-queries.md`](routines-and-scheduled-queries.md) sets out, with the rule for moving them one at a time.

## Integration patterns (stated)

The Conversational Analytics API's [integration patterns](https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/integration-patterns) page names ten; three shape the lab:

| Pattern | What runs | Lab stand-in |
|---|---|---|
| 6 ADK schema-driven | `BigQueryToolset.ask_data_insights` with inline table references; SQL from schema inference, no semantic guardrails | the eval baseline |
| 7 ADK governed | `DataAgentToolset.ask_data_agent` on a pre-configured data agent (knowledge sources, descriptions, instructions, verified queries, glossary) | the semantic agent, with a MetricFlow toolset in the data agent's place |
| 9 MCP | MCP Toolbox `bigquery-conversational-analytics` wrapping `chat`; ADK connects through `McpToolset` | not built; the toolset seam covers it |

[BigQuery data agents](https://docs.cloud.google.com/bigquery/docs/conversational-analytics) take custom table and field metadata, instructions, verified queries and glossary terms, in that priority.
They advise curated views over agent-chosen joins, and at most 100 knowledge sources (about 20 per agent in practice).
The authored context's [`system_instruction` YAML](https://docs.cloud.google.com/gemini/docs/conversational-analytics-api/data-agent-authored-context-bq) is what `build_catalog.py` writes and `check_catalog.py` checks.
`DataAgentToolset` ([ADK docs](https://adk-labs.github.io/adk-docs/integrations/data-agent)) takes a `DataAgentCredentialsConfig` and a `DataAgentToolConfig` (`location`, `max_query_result_rows`) and names an agent `projects/{project}/locations/{location}/dataAgents/{agent}`.

## Dialect

Each construct Postgres and BigQuery spell differently on the semantic path is one `adapter.dispatch` macro in `dbt/macros/dialect.sql`; the compiled Postgres SQL is unchanged apart from whitespace and type-name case (measured):

| Macro | Postgres (`default__`) | BigQuery (`bigquery__`) | Used by |
|---|---|---|---|
| `utc_date(column)` | `cast(column at time zone 'UTC' as date)` | `date(column, 'UTC')` | `slv_orders`, `slv_returns`, `gld_daily_weather` |
| `day_spine(start, end)` | `generate_series(date …, date …, interval '1 day')` | `unnest(generate_date_array(date …, date …))` | `metricflow_time_spine` |
| `type_timestamptz()` | `timestamptz` | `timestamp` | bronze orders, returns, weather |
| `dbt.type_string()` (dbt's own) | `TEXT` | `STRING` | bronze |

`dbt.date_spine` was not used: it counts its days with a warehouse query, so it cannot compile offline.

Contract types in the YAML cannot call a macro, so they are spelled for both: `date` and `numeric`, and `bigint` and `integer`, which GoogleSQL takes as aliases of `INT64` (measured (emulator)); a string is a YAML anchor whose Jinja renders `text` on Postgres and `string` on BigQuery.

The TLC models are off the semantic path and keep Postgres forms, marked `-- dialect:` where they stand:
- `tlc_columns`: `double precision` and `timestamp` are `FLOAT64` and `DATETIME`.
- `tlc_month_of`: `substring(… from <regex>)` is `REGEXP_EXTRACT`.
- `slv_tlc_trips`: `delete+insert` on `data_month` is `insert_overwrite` on a month-partitioned `pickup_date`.
- `tlc_retire`: month partitions expire instead.

Their bronze models also read the landed table's columns at compile time (`adapter.get_relation`), so they need a live connection to compile.

## Unverified

- That the compiled SQL runs on BigQuery itself: it runs on the emulator, whose analyzer is ZetaSQL's, including MetricFlow's `TIMESTAMP_TRUNC(order_date, day)` on a `DATE` column; real BigQuery stays the final word.
- The exact `ask_data_agent` arguments: the ADK page does not list them; the lab toolset's contract is a question in, and text, rows and SQL out, as the docs describe.
- Whether a native data agent can use the freshness tables, and how: as a knowledge source, a verified query, or a tool beside `DataAgentToolset`.
- Cloud Run Job overrides: read from the Jobs API reference, not tried.
