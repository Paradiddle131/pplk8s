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
| `target/catalog/data_agent/example_queries.json` | The data agent's verified queries (formerly golden queries) | MetricFlow compiles each metric and each dbt saved query offline in the target's dialect (measured on BigQuery's); a saved query is dbt's unit for a question answered the same way every time, so it carries its question (`config.meta.question`) |
| `list_metrics`, `describe_metric`, `query_metrics` (MetricFlow) | `DataAgentToolset`: `list_accessible_data_agents`, `get_data_agent_info`, `ask_data_agent` (ADK ≥ 1.23; stated) | Pass the toolset and its catalog-only tools (`list_accessible_data_agents`, `get_data_agent_info`) to `build_agent` in `semantic_agent/agent.py`; the agent, its session store, the audit and the freshness stay, and the instruction's tool names change. The audit and the freshness live in the agent's `after_tool_callback` (`guard.py`), around whatever toolset fills the seam: every call to a tool not named catalog-only is audited and gets the freshness of the metrics its result names (#177) |
| `sql_baseline` (`execute_sql` over gold and exposed) | `BigQueryToolset.ask_data_insights` with inline table references | The "ADK schema-driven" pattern: what most teams run first, and what the eval scores against; an eval arm only, never deployed, so nothing to move (SL-5) |
| `MODEL_BACKEND=openrouter` (free model) | `MODEL_BACKEND=gemini` | `model.py` is the only place naming a provider |
| ADK `DatabaseSessionService` on the metadata DB's `agent_sessions` | The same on Cloud SQL, or `VertexAiSessionService` | ADK's session URI |
| `agent_metrics` role (and `agent_sql`, the eval baseline's) | A service account per deployed agent with dataset-level read on the datasets it may see | Trust stays in the warehouse, not the prompt (SL-4); [Agent access and audit](#agent-access-and-audit) is the proposal |
| `ops.agent_queries`, written as the insert-only `agent_audit` role | BigQuery's Data Access audit log and `INFORMATION_SCHEMA.JOBS`, with the agent's session in job labels | [Agent access and audit](#agent-access-and-audit) |
| Freshness from `ops.readiness` and `ops.product_deadlines` | The same two tables in BigQuery | The agent's after-tool callback reads them for the metrics a data call's result names, whatever the toolset; if `ask_data_agent` names none, the answer says its freshness is unknown, and a native data agent could instead take them as a knowledge source or a verified query (unverified) |
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

## Agent access and audit

The lab gives each agent its own read-only warehouse role and audits every data query it runs as a row in `ops.agent_queries`, written by a role that may only insert there ([`semantic/PLAN.md`](../semantic/PLAN.md) SL-4, SL-10).
This is how that maps to BigQuery; IAM on a real project stays out of scope, so it is a proposal, not a measurement.

### Who sees what

| Option | What it is | For | Against |
|---|---|---|---|
| A. Dataset-level read per agent identity | One service account per agent; BigQuery Data Viewer on each dataset it reads, Job User in the project its queries run in | Maps one to one onto the lab's roles; one grant per dataset; the audit names the agent by its service account | A grant covers the whole dataset: the semantic agent reads every column of silver, which MetricFlow needs for its semantic models |
| B. Authorized views or an authorized dataset | The agent reads a dataset of views and has no grant on the source datasets; the views are authorized on them ([stated](https://docs.cloud.google.com/bigquery/docs/authorized-views): principals "can view the shared data and run queries on it, but they can't access the source dataset directly") | Narrows an agent to chosen columns and rows; dbt-bigquery grants a view model access with `grant_access_to` ([stated](https://docs.getdbt.com/reference/resource-configs/bigquery-configs)) | A view per table an agent reads, and the semantic models would have to sit on those views instead of silver |
| C. A separate project for the agents | The agents' service accounts run their jobs in an agent project and read the data project's datasets through A or B | Separates the agents' jobs, quotas and billing from the pipelines' | A second project to run, and it still needs A or B for the reads |

**Recommendation: A**, one service account per deployed agent with dataset-level read, which is what the lab's roles already rehearse: the semantic agent on silver and semantic (plus the two `ops` tables its freshness reads, as table-level grants).
The lab deploys one agent; the text-to-SQL baseline runs only inside the eval (SL-5), so its `agent_sql` role needs no counterpart unless the eval itself runs against BigQuery, where it would get its own identity on gold and exposed.
Add B only for an agent that must see part of a dataset, and C only when the agents' query cost or quota needs its own budget.

### What is logged where

| Lab (`ops.agent_queries`) | BigQuery |
|---|---|
| Every `query_metrics` and `execute_sql` call, refused ones included | A query job's `JobInsertion` and `JobChange` events in the `data_access` audit log stream ([stated](https://docs.cloud.google.com/bigquery/docs/reference/auditlogs)), which BigQuery cannot turn off ([stated](https://docs.cloud.google.com/logging/docs/audit/configure-data-access): "BigQuery Data Access audit logs can't be disabled"); a refused call that never ran a job is only in the agent's own record |
| `agent` | The caller's identity on the audit entry, and `user_email` in `INFORMATION_SCHEMA.JOBS` ([stated](https://docs.cloud.google.com/bigquery/docs/information-schema-jobs)): the agent's service account under option A |
| `sql` | The SQL text on the audit entry, and `query` in `INFORMATION_SCHEMA.JOBS` (stated, same pages) |
| The tables read (implied by the metrics or SQL) | `referenced_tables` in `INFORMATION_SCHEMA.JOBS` (stated) |
| `user_id`, `session_id`, `call_id`, `metrics` | Job labels set at submission (`labels` in the job configuration, [stated](https://docs.cloud.google.com/bigquery/docs/adding-labels); a label cannot be added to a job once it is submitted), which `INFORMATION_SCHEMA.JOBS` shows as `labels`; dbt-bigquery turns a query comment into job labels with `query-comment: {job-label: true}` (stated, dbt's BigQuery configs) |
| `rows_returned`, `freshness`, `error` | Not a job attribute: the agent's own record keeps them |
| Kept as long as the table is | `INFORMATION_SCHEMA.JOBS` keeps 180 days of job history (stated); the audit log's retention is its log bucket's |

So at work the platform's audit log is the record of what each agent read, and the agent keeps a thin record of its own for what a job cannot carry: the conversation it served, the metrics asked for, the freshness it quoted and the calls it refused; labels join the two.
That record's table comes from the dbt project, `dbt run-operation agent_warehouse` (`dbt/macros/agent_warehouse.sql`), which creates `ops.agent_queries` with BigQuery's types wherever the project builds (measured (emulator)); the agents' identities and their grants stay IAM, outside dbt.

## Unverified

- That the compiled SQL runs on BigQuery itself: it runs on the emulator, whose analyzer is ZetaSQL's, including MetricFlow's `TIMESTAMP_TRUNC(order_date, day)` on a `DATE` column; real BigQuery stays the final word.
- The exact `ask_data_agent` arguments: the ADK page does not list them; the lab toolset's contract is a question in, and text, rows and SQL out, as the docs describe.
- Whether `ask_data_agent`'s result names the metrics or tables it used, which the after-tool callback needs to look up their freshness; without them every answer says its freshness is unknown, and the options are the freshness tables as a knowledge source or a verified query of the data agent.
- Cloud Run Job overrides: read from the Jobs API reference, not tried.
- Whose identity a native data agent's queries run as (the caller's or a service account's), and so what the audit log names; and whether MetricFlow's BigQuery client lets each query set its own job labels.
- In which project's audit log a cross-project read (option C) lands.
