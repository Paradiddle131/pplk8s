# The semantic layer on BigQuery

How each piece of the lab's semantic track maps to its work counterpart on GCP, and what the lab proves about getting there ([`semantic/PLAN.md`](../semantic/PLAN.md) R7, S5).
"Measured" means run in this repo (`make bigquery-check` and the checks it names); "measured (emulator)" means run on the BigQuery emulator by `make bigquery-emulator-check`; "measured (live)" means run on real BigQuery in the lab project by `make bigquery-live-check`; "stated" means read from Google's or dbt's documentation (2026-10); "unverified" means neither.

## What carries over unchanged

The dbt project, its semantic YAML and the catalog generator run on BigQuery's adapter with no edit (measured, `make bigquery-check`, offline):
- `dbt parse` and `mf validate-configs --skip-dw` pass on the compile-only `bigquery` target of `dbt/profiles.yml`.
- `dbt compile` of the semantic path (sales, returns, finance, semantic) passes, and all 16 compiled models parse as BigQuery SQL.
- `build_catalog.py` writes the agent catalog with `project.dataset.table` relations, and verified queries that read `` `pplk8s-lab`.`silver`.`orders` `` in BigQuery's dialect; `check_catalog.py` passes.
- `build_catalog.py` writes the data agent's context as a v1 `Context` whose table references hold every table the verified queries read, and `check_catalog.py` validates it against the pinned v1 schema ([below](#the-data-agents-context-v1)).

It also runs (measured (emulator), `make bigquery-emulator-check`, [`semantic/PLAN.md`](../semantic/PLAN.md) SL-7):
- `dbt build` of the semantic path, tests included, on the `bigquery_emulator` output: every model and test passes on GoogleSQL, as the emulator's ZetaSQL analyzer checks it.
- MetricFlow queries the eight metrics there, and they equal the hand-written gold and exposed tables the same build wrote, day by day.
- The period metrics run there too: over `dbt/dev/fixture_weeks.sql`'s six weeks, the three week-over-week growths (`offset_window: 1 week`, ISO weeks from Monday) and the three month-to-date totals (`grain_to_date: month`) equal SQL by hand on gold, week by week and day by day, with no shim; changing one metric's `grain_to_date` to `week` fails the check.
- The emulator needs a shim for two gaps dbt-bigquery hits (`routines.list`, and DDL jobs reported as `SELECT`); real BigQuery has neither.

And it runs on real BigQuery (measured (live), `make bigquery-live-check` on the lab project, 2026-11-01, #206): the same script and fixture as on the emulator, on dbt's `gcp` output.
- Every part builds with its tests (recruitment 43, customer actions 37, partner outreach 56, call transcripts 60, platform 173 nodes, no error), the recruitment snapshot replayed extract by extract keeps every stage change, and all 63 layer hops reconcile.
- Every metric MetricFlow queries equals its gold or exposed oracle, `migration.parity` reports as on Postgres, and `ops.agent_queries` takes a row.
- One difference the emulator hid: BigQuery refuses a parameterized type in CAST (`numeric(12, 2)`), so the bronze casts go through `cast_decimal` and `make bigquery-check` fails on the next one (#275).
- The run billed 8,420,065,280 bytes (7.8 GiB, inside the free 1 TiB a month), and the cost check before and after read $0.00.

The target is compile-only: `method: oauth-secrets` with a placeholder token lets dbt build its client offline, and `--no-introspect --no-populate-cache` keeps compile from querying.
At work the same output takes `method: oauth` (application default credentials) and a real project.

## The mapping

| Lab piece | Work counterpart | How it gets there |
|---|---|---|
| Warehouse comments (`persist_docs` on gold and exposed) | BigQuery table and column descriptions, which Knowledge Catalog shows | The same dbt models with `persist_docs`; dbt-bigquery writes descriptions as it builds (stated) |
| Model contracts on gold and exposed (`contract: {enforced: true}`, a `data_type` on every column) | The BigQuery table schema, which Knowledge Catalog shows beside the descriptions | Contracts act at build time: dbt compares the model's columns with the contract before it builds, and dbt-bigquery creates a contracted table with the declared types (measured (emulator)); the schema and Knowledge Catalog are what agents read at query time. A view gets the name and type check but no constraints (stated) |
| `semantic.metrics` (one row per metric: name, label, description, type, models, pipelines) | Glossary terms: BigQuery custom glossary or Knowledge Catalog | The same model builds on BigQuery; the context's `glossaryTerms` carry the same words |
| `semantic.glossary` (one row per business term that is not a metric: term, description, synonyms, metrics, dimensions) | The same glossary, for terms such as a cohort or a channel | `config.meta.glossary` on the dbt models; the same model builds on BigQuery, and the context's `glossaryTerms` carry each term with its metrics and dimensions in the description (a v1 `GlossaryTerm` has no field for them) |
| `target/catalog/data_agent/context.json` | The data agent's whole context: a v1 `Context` (tables with their schemas, glossary terms, example queries, system instruction) | Generated from the manifests by `build_catalog.py` (S2); set as the agent's staging context, then published (`dataAnalyticsAgent.stagingContext`, `publishedContext`; stated); [field by field below](#the-data-agents-context-v1) |
| `target/catalog/data_agent/system_instruction.yaml` | What the structured context has no field for: the instruction, aggregations, relationships, additional descriptions | The same generator; it is context.json's `systemInstruction`, as text |
| `target/catalog/data_agent/example_queries.json` | The data agent's verified queries (formerly golden queries), context.json's `exampleQueries` | MetricFlow compiles each metric and each dbt saved query offline in the target's dialect (measured on BigQuery's); a saved query is dbt's unit for a question answered the same way every time, so it carries its question (`config.meta.question`) |
| `list_metrics`, `describe_metric`, `query_metrics` (MetricFlow) | `DataAgentToolset`: `list_accessible_data_agents`, `get_data_agent_info`, `ask_data_agent` (ADK ≥ 1.23; stated) | Pass the toolset and its catalog-only tools (`list_accessible_data_agents`, `get_data_agent_info`) to `build_agent` in `semantic_agent/agent.py`; the agent, its session store, the audit and the freshness stay, and the instruction's tool names change. The audit and the freshness live in the agent's `after_tool_callback` (`guard.py`), around whatever toolset fills the seam: every call to a tool not named catalog-only is audited and gets the freshness of the metrics its result names (#177) |
| `sql_baseline` (`execute_sql` over gold and exposed) | `BigQueryToolset.ask_data_insights` with inline table references | The "ADK schema-driven" pattern: what most teams run first, and what the eval scores against; an eval arm only, never deployed, so nothing to move (SL-5) |
| `MODEL_BACKEND=openrouter` (free model) | `MODEL_BACKEND=gemini` | `model.py` is the only place naming a provider |
| ADK `DatabaseSessionService` on the metadata DB's `agent_sessions` | ADK's `FirestoreSessionService` on Firestore's free `(default)` database (the lab project, SL-13), or `VertexAiSessionService` | ADK's session URI, `SESSION_SERVICE_URI`: `firestore://`, a scheme the agents directory's `services.py` registers, is the GCP image's default (#209); the service built from it in that image measured (`make gcp-image-check`), sessions written to and read from Firestore unverified until the live slice |
| `agent_metrics` role (and `agent_sql`, the eval baseline's) | A service account per deployed agent with dataset-level read on the datasets it may see | Trust stays in the warehouse, not the prompt (SL-4); [Agent access and audit](#agent-access-and-audit) is the proposal |
| `ops.agent_queries`, written as the insert-only `agent_audit` role | BigQuery's Data Access audit log and `INFORMATION_SCHEMA.JOBS`, with the agent's session in job labels | [Agent access and audit](#agent-access-and-audit); the lab agent's own row goes through its warehouse seam (`AGENT_WAREHOUSE=bigquery`, #209): a parameterised DML insert, never a streaming one, capped and labelled with the agent and its session, as `agent-audit` by impersonation; the insert and its read-back measured (emulator), the impersonation and the labels in the audit log unverified |
| Freshness from `ops.readiness` and `ops.product_deadlines` | The same two tables in BigQuery, which `dbt run-operation agent_warehouse` creates where missing, with the Compose init's deadlines (#209) | The agent's after-tool callback reads them through the same seam (one query, the products as an array parameter; a product's freshness from a ledger row and its pipeline's 36 h deadline measured (emulator)) for the metrics a data call's result names, whatever the toolset; `ask_data_agent` names no metric, but its result carries the data agent's `generatedSql`, whose tables say which readiness products it read (stated, [below](#what-ask_data_agent-returns-stated); looking freshness up by table is [#207](../../../issues/207)); a native data agent could also take them as a knowledge source or a verified query (unverified) |
| `dbt source freshness` on the `source-freshness` CronJob, its verdict in `ops.source_freshness`, `SourceStale` from the warehouse `sql_exporter` (SL-12) | Cloud Scheduler → a Cloud Run Job on the dbt image whose command is `dbt source freshness`; the same `on-run-end` hook writes `ops.source_freshness` in BigQuery, and a Cloud Monitoring alert reads it (a log-based metric on the Job's freshness errors, or a scheduled query into a custom metric) | The thresholds and the hook are the dbt project's, so they move unchanged; `loaded_at_field: _loaded_at` costs a scan of the column per check, so on a partitioned table give the source a `loaded_at_query` over the newest partition instead (stated); the Job exits 0 on stale sources as the CronJob does, so the alert is the freshness, not the Job (unverified) |
| `validate_semantic_layer` in `finance_daily` | A Cloud Run Job on the dbt image whose command is `dbt parse && mf validate-configs` | Job overrides change args, not the command, so it is its own Job (unverified) |
| The agent's `semantic-agent` Deployment in kind, its key in a Kubernetes Secret, its sessions in the metadata DB | A Cloud Run service under the agent's service account: request-based billing, 0 to 1 instances, IAM callers only; its key from Secret Manager, its sessions in Firestore (ADK's `FirestoreSessionService`) | `platform/gcp/infra/run.tf` and `secrets.tf`, deployed by `make gcp-workloads-up` (#209; planned, unverified until it runs on the lab project) |
| The dbt Job (`make dbt-job`) and the `source-freshness` CronJob | Cloud Run Jobs `dbt-build` and `dbt-source-freshness` on the dbt image as `dbt-runner`, each run by Cloud Scheduler through the Run Admin API's `:run` method as the `scheduler` account | `platform/gcp/workloads.yaml` and `infra/scheduler.tf` (#209; planned, unverified until it runs on the lab project) |

What does not carry over: a native data agent does not run MetricFlow.
The metric definitions reach it as words and SQL: the glossary, the aggregations in the authored context, and one verified query per metric.
The lab's agent queries through MetricFlow itself, so its eval shows what the definitions are worth when they are enforced, not only described.

Scheduled queries and routines (stored procedures, UDFs, table functions) map onto dbt models, functions, macros and metrics as [`routines-and-scheduled-queries.md`](routines-and-scheduled-queries.md) sets out, with the rule for moving them one at a time.
Signals extracted from text (a transcript's topic, objection, sentiment) are labelled in dbt through BigQuery's AI functions, versioned and tested against a golden set, as [`text-signals.md`](text-signals.md) sets out.

## Integration patterns (stated)

The Conversational Analytics API's [integration patterns](https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/integration-patterns) page names ten; three shape the lab:

| Pattern | What runs | Lab stand-in |
|---|---|---|
| 6 ADK schema-driven | `BigQueryToolset.ask_data_insights` with inline table references; SQL from schema inference, no semantic guardrails | the eval baseline |
| 7 ADK governed | `DataAgentToolset.ask_data_agent` on a pre-configured data agent (knowledge sources, descriptions, instructions, verified queries, glossary) | the semantic agent, with a MetricFlow toolset in the data agent's place |
| 9 MCP | MCP Toolbox `bigquery-conversational-analytics` wrapping `chat`; ADK connects through `McpToolset` | the three metric tools over MCP (`make agent-mcp`, SL-20), [below](#the-semantic-layer-over-mcp) |

[BigQuery data agents](https://docs.cloud.google.com/bigquery/docs/conversational-analytics) take custom table and field metadata, instructions, verified queries and glossary terms, in that priority.
They advise curated views over agent-chosen joins, and at most 100 knowledge sources (about 20 per agent in practice).
The context `build_catalog.py` writes and `check_catalog.py` checks is the API's v1 structured `Context`, with the [authored-context YAML](https://docs.cloud.google.com/gemini/docs/conversational-analytics-api/data-agent-authored-context-bq) as its `systemInstruction` for what has no structured field ([below](#the-data-agents-context-v1)).
`DataAgentToolset` ([ADK docs](https://adk-labs.github.io/adk-docs/integrations/data-agent)) takes a `DataAgentCredentialsConfig` and a `DataAgentToolConfig` (`location`, `max_query_result_rows`) and names an agent `projects/{project}/locations/{location}/dataAgents/{agent}`.

## The data agent's context (v1)

`build_catalog.py` writes the data agent's whole context as one v1 `Context` of the Conversational Analytics API, `target/catalog/data_agent/context.json` (#204), ready for a DataAgent's `dataAnalyticsAgent.stagingContext` and then `publishedContext`.
Google's authored-context page asks for context through the structured fields wherever one exists, so the YAML keeps only what has none (stated).
The field names and bounds are the API's discovery document, revision 20261022 (stated), pinned in `dbt/scripts/schemas/geminidataanalytics-v1-context.json` (`Context` and the eight messages it reaches that the generator fills; `dbt/scripts/pin_context_schema.py` renews the pin from `https://geminidataanalytics.googleapis.com/$discovery/rest?version=v1`).

| Lab artefact | v1 field | What fills it |
|---|---|---|
| The tables the semantic models and the time spine read | `datasourceReferences.bq.tableReferences[]`: `projectId`, `datasetId`, `tableId` | The dbt target's database, schema and alias, as the catalog renders every relation: `pplk8s-lab`, `silver`, `orders` on the compile-only target, the Postgres database (`warehouse`, `dbt_dev`) on the lab's; the generator runs offline, so the project is the target's |
| The dbt model's description and tags | `.schema.description`, `.schema.tags` (its layer and pipelines), `.schema.synonyms` (its semantic model's and primary entity's names, where they differ from the table's) | `persist_docs` writes the same words to the table (above) |
| The model's declared columns | `.schema.fields[]`: `name`, `type` (the declared `data_type`, where one is), `description`, `synonyms` (the entities and dimensions the column backs), `tags` (`primary key`, `foreign key`, `categorical`, `numeric` or `time dimension`, `measure`) | A column marked `meta: {pii: true}` is left out, as no agent reads it (SL-22) |
| `semantic.metrics` and `semantic.glossary` | `glossaryTerms[]`: `displayName` (a metric's label, a term), `description`, `labels` (the metric's name, the term's synonyms) | A term's description ends with the metrics and dimensions it maps to |
| `example_queries.json` | `exampleQueries[]`: `naturalLanguageQuestion`, `sqlQuery` | The same list; no `parameters` yet |
| `system_instruction.yaml` | `systemInstruction`, as text | The instruction, each table's field `aggregations`, the `relationships` and the `additional_descriptions` (formulas): v1's `Field` has no aggregation, and its `schemaRelationships` are a "derived context retrieved from Dataplex Dataset Insights" (from job history, an LLM's suggestion or table constraints), not an authored join (stated) |

`check_catalog.py` walks context.json against the pin: a key the schema lacks, a missing field it calls "Required.", a text over its "at most N bytes" (2,000 for a question, 50,000 for a query, 256 and 5,000 for a term's name and description, 250,000 for the system instruction) and an output-only or deprecated field fail it; so does a table, glossary term or example query the other artefacts hold and context.json lacks (measured, `make bigquery-check`, which also fails on each of three planted faults).
On the compile-only target it holds 17 tables, 71 glossary terms and 64 example queries, about 160 KB; on Postgres 70 and 63, without the BigQuery-only median (measured, offline).
It carries no credentials: v1's `Context` has no such field, and the chat request's own `credentials` are for sources such as Looker (stated).

Knowledge Catalog: "the data agent can import a maximum of 10 glossary terms per table" and ignores the rest ([stated](https://docs.cloud.google.com/knowledge-catalog/docs/manage-glossaries)).
The context's `glossaryTerms` belong to no table, but the same terms are what the catalog would attach, so `check_catalog.py` fails a table that would carry more than ten, by this mapping: a simple metric on the table it aggregates, a glossary term on the model that defines it (`config.meta.glossary`), and a ratio, derived, cumulative or conversion metric on none, since it combines other metrics.
`silver.orders` carries the most, nine on the compile-only target (seven simple metrics, *Order status* and *Sales*) and eight on Postgres; a tenth metric or term there is the last before the check fails (measured).

## What `ask_data_agent` returns (stated)

ADK 2.13's source (`google/adk/tools/data_agent/data_agent_tool.py`) defines `ask_data_agent(data_agent_name, query)`: the agent's resource name `projects/{project}/locations/{location}/dataAgents/{agent}` and the question; the credentials, the `DataAgentToolConfig` and the tool context are filled by the toolset, not the model.
It posts one `chat` with `dataAgentContext.dataAgent` set and returns `{"status": "SUCCESS", "response": [...]}`, the stream's messages in order (`_gda_stream_util.get_stream`): each system message as it arrives, except one carrying rows, which becomes `Data Retrieved` (headers and at most `max_query_result_rows` rows), and only the last of those is kept.
A chat [`Message`](https://docs.cloud.google.com/gemini/docs/conversational-analytics-api/reference/rest/v1/Message)'s `systemMessage.data` holds the data step: `query.datasources` (the data sources available to answer it), `generatedSql`, `bigQueryJob` (`projectId`, `jobId`, `location`, the destination table and the result schema), `result`, and `matchedQuery` when a verified query matched.
So a tool result carries the SQL the data agent ran, and its `FROM` clauses name its tables: the freshness lookup can go by table, which [#207](../../../issues/207) takes up; this repo does not build it yet.
A `bigQueryJob` would join the call to `INFORMATION_SCHEMA.JOBS` and the Data Access log by job id.

## The semantic layer over MCP

The lab serves `list_metrics`, `describe_metric` and `query_metrics` over MCP (streamable HTTP) for agents outside ADK (SL-20): `make agent-mcp`, with one bearer token per client in `SEMANTIC_MCP_CLIENTS=<agent>=<token>,...`.
Every data call goes through the same code as ADK's after-tool callback (`guard.guarded`): its audit row in `ops.agent_queries`, written as the agent its token names, and its metrics' freshness statement in the result.
`make agent-mcp-check` drives it with a scripted MCP client and no model: the three tools listed, net revenue on 2 October 2026 answered as 861.4 with its freshness, the call's audit row found, and a call without a known token refused with 401.

A run from an MCP-capable agent CLI (2026-11-02): `adk run` on `services/semantic-agent/examples/mcp_client`, an agent whose only tools are an `McpToolset` on the server, on OpenRouter's free `nvidia/nemotron-3.5-super-vl:free`, with the server on the agents' fixture (`dbt_dev`).
Asked the eval's `net_revenue_one_day` question ("What was net revenue on 1 October 2026, after partner returns?"), it called `list_metrics`, then `query_metrics` on `net_revenue_eur` for that day, and answered "Net revenue on 1 October 2026 was 964.19 EUR", followed by the freshness statement word for word; the eval's expected SQL gives 964.19, and the call's audit row names the client's agent (`adk_cli_demo`), its MCP session and the request's id.

| | Lab | At work (stated) | Keeps | Loses |
|---|---|---|---|---|
| Governed metrics over MCP | the lab's MCP server over MetricFlow | [MCP Toolbox for Databases](https://mcp-toolbox.dev/integrations/bigquery/tools/bigquery-conversational-analytics/) `bigquery-conversational-analytics` (or `conversational-analytics-ask-data-agent`) over a data agent | one definition per metric, the data agent's context, the client's own identity (its service account) | the lab's exact metric arithmetic (a data agent writes SQL from the definitions, it does not run MetricFlow); the audit row and freshness statement, which move to the Data Access audit log and the readiness tables ([Agent access and audit](#agent-access-and-audit)) |
| Raw SQL over MCP | the eval baseline (`execute_sql`) | [BigQuery's remote MCP server](https://docs.cloud.google.com/bigquery/docs/use-bigquery-mcp) (`https://bigquery.googleapis.com/mcp`, OAuth and IAM; GA 2026-04-20), `execute_sql_readonly` and others | IAM on the datasets, the platform's audit log | every semantic guardrail: the model writes the SQL, which is the baseline the eval scores against |

Client identity: the lab's bearer token per client stands in for the client's service account; the server's `TokenVerifier` is the seam a real issuer's tokens would fill (unverified).

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
| A. Dataset-level read per agent identity | One service account per agent; BigQuery Data Viewer on each dataset it reads, Job User in the project its queries run in | Maps one to one onto the lab's roles; one grant per dataset; the audit names the agent by its service account | A grant covers the whole dataset: the semantic agent reads every column of silver, which MetricFlow needs for its semantic models, except the personal columns a policy tag keeps (below) |
| B. Authorized views or an authorized dataset | The agent reads a dataset of views and has no grant on the source datasets; the views are authorized on them ([stated](https://docs.cloud.google.com/bigquery/docs/authorized-views): principals "can view the shared data and run queries on it, but they can't access the source dataset directly") | Narrows an agent to chosen columns and rows; dbt-bigquery grants a view model access with `grant_access_to` ([stated](https://docs.getdbt.com/reference/resource-configs/bigquery-configs)) | A view per table an agent reads, and the semantic models would have to sit on those views instead of silver |
| C. A separate project for the agents | The agents' service accounts run their jobs in an agent project and read the data project's datasets through A or B | Separates the agents' jobs, quotas and billing from the pipelines' | A second project to run, and it still needs A or B for the reads |

**Recommendation: A**, one service account per deployed agent with dataset-level read, which is what the lab's roles already rehearse: the semantic agent on silver and semantic (plus the two `ops` tables its freshness reads, as table-level grants).
The lab deploys one agent; the text-to-SQL baseline runs only inside the eval (SL-5), so its `agent_sql` role needs no counterpart unless the eval itself runs against BigQuery, where it would get its own identity on gold and exposed.
Add B only for an agent that must see part of a dataset, and C only when the agents' query cost or quota needs its own budget.
On the lab project, A is declared in [`platform/gcp/access.yaml`](../platform/gcp/access.yaml) (#205): `dbt-runner`, `semantic-agent` and `agent-audit`, each with BigQuery Job User and the dataset grants of the lab role it stands for, which `platform/gcp/tests/test_access.py` compares with `dbt/macros/agent_warehouse.sql`; the table-level grants on `ops` come with their tables (#209).

### Personal data by column

The lab keeps a column marked `meta: {pii: true}` from every agent role by column privileges (`dbt/macros/agent_pii_columns.sql`, SL-22): each model with one runs a post-hook that leaves its agent roles SELECT on every other column, and gives the whole relation to its `config.meta.pii_readers`, the outreach automation; `make agent-columns-check` logs in as each role and shows `select *` refused.
BigQuery does the same with policy tags, and can mask instead of refuse:

| | Column-level access control | Dynamic data masking |
|---|---|---|
| What it is | A policy tag from a taxonomy on the column; reading it takes Fine-Grained Reader on the tag, "even when the user has dataset access" ([stated](https://docs.cloud.google.com/bigquery/docs/column-level-security-intro)) | A data policy on the policy tag: a Masked Reader reads the column masked, a Fine-Grained Reader reads it raw, anyone else is denied; rules include nullify, SHA-256 hash, an email mask (`XXXXX` for the user name), first or last four characters and a default value ([stated](https://docs.cloud.google.com/bigquery/docs/column-data-masking-intro)) |
| Lab counterpart | The column grants above; `select *` fails for an agent, as BigQuery's error lists the denied columns and `SELECT * EXCEPT (...)` reads the rest (stated, first page) | None: the lab refuses, it never masks |
| Where it applies | BigQuery, BigLake and Omni tables, not views (stated, first page); a view over a tagged column checks the tag on the table under it, and an authorized view only that ([stated](https://docs.cloud.google.com/bigquery/docs/column-level-security-intro)) | The same tags, so the same tables |
| Edition | Enterprise, Enterprise Plus and on-demand pricing; Standard has "No access to fine-grained security controls" ([stated](https://docs.cloud.google.com/bigquery/docs/editions-intro)) | The same row of the same table |
| Cost | Uses BigQuery and Data Catalog, "so both products' pricing applies" (stated, first page); no figure for a taxonomy or a tag on the pages read (Unverified) | As column-level access control, plus the masked query's own bytes |
| From dbt | `policy_tags` on the column in the YAML, written only with column-level `persist_docs` (measured (source): dbt-bigquery 1.12.1 `update_columns` sets each documented column's tags to its `policy_tags`, an empty list when none, so a tag set outside dbt is cleared on the next build) | Data policies are not a dbt config: IAM and the data policy API, beside the service accounts |

**Recommendation: column-level access control, no masking.**
`silver.partner_contacts` carries `policy_tags: ["{{ var('pii_policy_tag') }}"]` on its personal columns, persisted only when the var names a tag, so the lab writes none; `exposed.outreach_activation` is a view and inherits the table's tags.
The agents' service accounts get no Fine-Grained Reader, so they read every other column, as the lab's roles do; the automation's account and `dbt-runner`, which builds the views and tables over the contacts, get it on the tag.
Masking is for a consumer that needs a stand-in value (an email's domain, a hash to join on); no agent here does, and a masked column would still be a dimension MetricFlow could group by, which `check_standard.py` forbids for a personal column anyway.

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

- ~~That the compiled SQL runs on BigQuery itself~~: measured (live), `make bigquery-live-check`, 2026-11-01: `PASS: BigQuery run check on BigQuery (pplk8s-lab-001)` (above).
- ~~The exact `ask_data_agent` arguments~~: stated, ADK 2.13's source: `ask_data_agent(data_agent_name, query)` ([above](#what-ask_data_agent-returns-stated)).
- ~~Whether `ask_data_agent`'s result names the tables it used~~: stated, a chat message's `generatedSql`, `datasources` and `bigQueryJob`, which ADK passes through ([above](#what-ask_data_agent-returns-stated)); it names no metric; still unverified are which of them a live data agent's stream sends, and whether a message carrying `bigQueryJob` also carries the rows that ADK reduces to `Data Retrieved`.
- That a DataAgent accepts context.json as its `publishedContext` as is: it validates against the pinned schema, but no data agent has been created from it (the lab project's $0.00 rule has not been checked for the Conversational Analytics API).
- Cloud Run Job overrides: read from the Jobs API reference, not tried; `make gcp-workloads-up` tries one, `dbt run-operation agent_warehouse` as an args override of the `dbt-build` Job (#209).
- ADK's `FirestoreSessionService` writing and reading a session on Firestore: built in the agent's GCP image (`make gcp-image-check`), not run against Firestore or its emulator.
- Whose identity a native data agent's queries run as (the caller's or a service account's), and so what the audit log names; and whether MetricFlow's BigQuery client lets each query set its own job labels.
- In which project's audit log a cross-project read (option C) lands.
- What a taxonomy and its policy tags cost in Data Catalog (Knowledge Catalog), and so whether column-level access control fits the lab project's $0.00 (SL-13); the lab has not created one.
