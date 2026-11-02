# How the data agent is built, configured and deployed

The BigQuery data agent's configuration (its instructions about the tables and their relationships, its verified queries, its glossary terms and its knowledge sources) is neither OpenTofu nor gcloud: it is generated from the dbt semantic YAML by code and published by code, through the Gemini Data Analytics v1 REST API ([#207](../../../issues/207)).
OpenTofu turns on the APIs and creates the datasets, the owner's one-off gcloud grants two roles, and a data load makes the tables exist; none of them touch the agent's context.

## From the dbt YAML to the console

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../assets/data-agent-deploy-dark.png">
  <img width="1200" alt="How the BigQuery data agent is built, checked and published. The only hand-written source is the dbt YAML: the semantic models on the silver models with their entities, dimensions, simple metrics, column descriptions and glossary terms in config.meta.glossary; semantic.yml with the time spine and the ratio, derived and cumulative metrics; saved_queries.yml with a question each. make bigquery-check, offline with no GCP account, runs dbt parse on the compile-only bigquery target; build_catalog.py reads manifest.json and semantic_manifest.json, asks MetricFlow for each query's SQL offline, and generates system_instruction.yaml, example_queries.json and context.json, the v1 Context that holds both; check_catalog.py validates it against the pinned v1 schema. make gcp-data-agent runs the live gate before and after, and publish.py moves the tables to GCP_PROJECT, caps each query with bigQueryMaxBilledBytes and validates the body against the pinned DataAgent schema, then calls the Gemini Data Analytics v1 REST API at location us: GET the agent, POST to create it with the staging context or PATCH the changed fields, poll each operation, then PATCH publishedContext. The resource is dataAgents/pplk8s-semantic. In the BigQuery console, name and description come from displayName and description, knowledge sources from tableReferences, instructions from systemInstruction, verified queries from exampleQueries and the glossary from glossaryTerms; an edit there is drift that the next publish writes back." src="../assets/data-agent-deploy.png">
</picture>

1. **Write the YAML; nothing else is written by hand.**
   The semantic models with their entities, dimensions, simple metrics, column descriptions and glossary terms (`config.meta.glossary`) sit on the silver models in [`dbt/models/silver/schema.yml`](../dbt/models/silver/schema.yml); the time spine and the ratio, derived and cumulative metrics in [`dbt/models/semantic/semantic.yml`](../dbt/models/semantic/semantic.yml); the saved queries, each with its question in `config.meta.question`, in [`dbt/models/semantic/saved_queries.yml`](../dbt/models/semantic/saved_queries.yml).
   The one fixed sentence of instruction is a constant in `build_catalog.py`.
2. **Generate, offline: `make bigquery-check`** ([`tests/e2e/bigquery-check.sh`](../tests/e2e/bigquery-check.sh)).
   `dbt parse` on the compile-only `bigquery` target writes `target/manifest.json` and `target/semantic_manifest.json`, with no GCP account and no warehouse.
   [`dbt/scripts/build_catalog.py`](../dbt/scripts/build_catalog.py) reads both, asks MetricFlow for each metric's and each saved query's SQL without a connection, and writes `target/catalog/agent.json` (the semantic agent's catalog) and, under `target/catalog/data_agent/`, `system_instruction.yaml` (the tables, their joins from the entities and the formulas, as text), `example_queries.json` (the verified queries) and `context.json`, the v1 `Context` that holds both of them, every table and every glossary term.
   The script leaves them in `dbt/target/bigquery/catalog/`.
3. **Check, offline.**
   [`dbt/scripts/check_catalog.py`](../dbt/scripts/check_catalog.py) fails a `context.json` that the pinned v1 schema ([`dbt/scripts/schemas/`](../dbt/scripts/schemas/), renewed by [`pin_context_schema.py`](../dbt/scripts/pin_context_schema.py) from the API's discovery document) does not accept, that misses a table, term or query the other files hold, or that puts more than 10 glossary terms on one table.
4. **Publish, live: `make gcp-data-agent`** ([`Makefile`](../Makefile), [`platform/gcp/data-agent/publish.py`](../platform/gcp/data-agent/publish.py)).
   It runs `make bigquery-check` first, and [`platform/gcp/live-gate.sh`](../platform/gcp/live-gate.sh) (the usage check and the cost check) before and after.
   `publish.py` moves every table reference, verified query and table name in the instruction from the compile-only project to `GCP_PROJECT`, sets `options.datasource.bigQueryMaxBilledBytes` to `free-path.yaml`'s per-query cap, and validates the body against the pinned `DataAgent` schema ([`platform/gcp/data-agent/schemas/`](../platform/gcp/data-agent/schemas/)).
5. **The REST calls, in order,** on the `us` endpoint (`https://geminidataanalytics.us.rep.googleapis.com`), with the caller's token:
   `GET dataAgents/pplk8s-semantic`; when it answers 404, `POST dataAgents?dataAgentId=pplk8s-semantic` with the context as `dataAnalyticsAgent.stagingContext`, otherwise `PATCH ?updateMask=` naming only the fields that differ; each long-running operation polled with `GET operations/…` until done; then `PATCH ?updateMask=dataAnalyticsAgent.publishedContext` to publish, since v1 has no publish method.
   A second run with the same context writes nothing and says so.
6. **The resource:** `projects/<GCP_PROJECT>/locations/us/dataAgents/pplk8s-semantic`; every chat reads its `publishedContext`.

What the BigQuery console shows, and the field it comes from:

| Console | The agent's field | Written by |
|---|---|---|
| Name, description | `displayName`, `description` | constants in `publish.py` |
| Knowledge sources | `…Context.datasourceReferences.bq.tableReferences` | `build_catalog.py`, from the semantic models' and the time spine's tables |
| Instructions | `…Context.systemInstruction` | `system_instruction.yaml` |
| Verified queries | `…Context.exampleQueries` | `example_queries.json`, compiled by MetricFlow |
| Glossary | `…Context.glossaryTerms` | the metrics and `config.meta.glossary` |

An edit in the console is drift: the next `make gcp-data-agent` sees the context, name or description differ and writes the generated one back; any other field stays as the console set it.
Change the YAML instead.

## Who provisions what

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../assets/data-agent-setup-dark.png">
  <img width="1200" alt="Who provisions what the BigQuery data agent needs, and who asks it. The owner, once, from their own shell with the Owner role: make gcp-up applies OpenTofu, which turns on the free-path APIs geminidataanalytics, dataplex and cloudaicompanion until 2026-12-30 and creates the BigQuery datasets; and gcloud, runbook step 8, grants the cloud session's account pplk8s-automation Data Agent Creator and Data Agent User, both expiring 2026-12-31. A cloud session with that account's token runs make bigquery-live-load, which loads dbt_dev's fixture into ds_source and runs dbt build on the gcp target, so the tables the knowledge sources name exist; make gcp-data-agent, which publishes the context to the data agent dataAgents/pplk8s-semantic; and make agent-eval ARM=data_agent, where the semantic agent's ADK DataAgentToolset asks the data agent, guard.py states freshness from the tables its generated SQL reads, and audit.py records every call. A chat runs the agent's SQL against BigQuery as the caller, each query capped." src="../assets/data-agent-setup.png">
</picture>

- **OpenTofu** (`make gcp-up`, by the owner): `geminidataanalytics`, `dataplex` and `cloudaicompanion` are on, each dated `until: 2026-12-30` in [`platform/gcp/free-path.yaml`](../platform/gcp/free-path.yaml) and turned on by [`platform/gcp/infra/apis.tf`](../platform/gcp/infra/apis.tf); the BigQuery datasets come from [`platform/gcp/infra/bigquery.tf`](../platform/gcp/infra/bigquery.tf).
- **The owner's one-off gcloud** ([`platform/gcp/README.md`](../platform/gcp/README.md), runbook step 8): `roles/geminidataanalytics.dataAgentCreator` and `dataAgentUser` for `pplk8s-automation`, expiring 2026-12-31.
- **The data load** (`make bigquery-live-load`, [`tests/e2e/bigquery-live-load.sh`](../tests/e2e/bigquery-live-load.sh)): the knowledge sources are table references, so the tables must exist; it copies `dbt_dev`'s fixture into `ds_source` and runs `dbt build` on the `gcp` target, every job capped.
- **The consumer** (`make agent-eval ARM=data_agent`, `AGENT_TOOLSET=data_agent`): [`toolset_data_agent.py`](../services/semantic-agent/src/semantic_agent/toolset_data_agent.py) reaches the agent through ADK's `DataAgentToolset` (`ask_data_agent`, `get_data_agent_info`); the guard states freshness from the tables its `generatedSql` reads, and every call is audited.
  A chat runs the agent's SQL as the caller's credential, each query under the context's `bigQueryMaxBilledBytes`.
