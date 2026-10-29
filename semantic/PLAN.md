# Semantic layer and metrics agent — plan

The second track of this repository, separate from the Airflow lab ([`../PLAN.md`](../PLAN.md), sealed for this topic).
It shares the warehouse, the dbt project and the Compose stand-ins; nothing in it changes a DAG, and nothing here feeds [`../LESSONS.md`](../LESSONS.md).
Progress lives in the issues under [Map #99](https://github.com/Paradiddle131/pplk8s/issues/99); this file holds what binds the work: the goal, the requirements, the decisions and the exit.
Decisions are a register: one row per live decision, amended in place, a superseded row deleted in the PR that supersedes it; git is the history.

## 1. Goal

Prove that an open-source dbt project can carry a semantic layer that an LLM agent queries instead of writing SQL, on the lab warehouse, and that the same YAML feeds the warehouse catalog and the authored context a native BigQuery data agent takes at work.
The audience is a team whose data already lands in BigQuery, whose agents guess which table to trust, and who will not run dbt Cloud.

## 2. Requirements

- R1 Every calculated field lives in exactly one metric definition.
- R2 Metrics are queryable locally (`mf` CLI and Python API), with no dbt Cloud.
- R3 An agent-facing catalog is generated from the dbt manifests and persisted as warehouse comments.
- R4 The agent answers through metric tools only; an eval set scores it against a text-to-SQL baseline with the same model.
- R5 The freshness of each metric, from `ops.readiness`, reaches the answer.
- R6 Agents read gold, exposed and metrics only, marked in dbt.
- R7 Dialect-neutral SQL, a compile-only `dbt-bigquery` target, and a written mapping to BigQuery descriptions, Knowledge Catalog and the native data agent's context.

Out of scope: real GCP spend, IAM, Gemini Enterprise, dbt Cloud, dbt Fusion, a custom chat UI, writes or approvals.

## 3. Decisions

| # | Decision | Why |
|---|---|---|
| SL-1 | **The semantic layer is dbt's: MetricFlow semantic models and metrics in the dbt project, over silver and gold, every calculated field defined once as a metric.** `dbt-metricflow[dbt-postgres]` 0.15.0 (MetricFlow 0.213.0) on the project's `dbt-core` 1.12.5 pin, a daily time spine model, `mf validate-configs` as a stage check, the `mf` CLI or Python API as the only query path; no dbt Cloud. | The spec is open source and runs on Postgres and BigQuery alike ([spike](research/semantic-layer-spike.md): eight metrics validate; `net_revenue_eur` matches `exposed.net_sales_daily` to the cent). The hand-written gold and exposed aggregates stay as the parity oracle. Rejected: Cube and the Boring Semantic Layer (a second model beside dbt), LookML (needs Looker), dbt Cloud (not what the client runs). |
| SL-2 | **The agent is an ADK agent and a Cloud Run stand-in** (`services/semantic-agent/`, namespace `workloads`): ADK owns the runner, the sessions (`DatabaseSessionService` on a database of the Compose metadata-db Postgres), serving (`adk api_server`; `adk web` is the demo surface) and evaluation (`adk eval`); the model sits behind a `MODEL_BACKEND` seam (OpenRouter free tier here, Gemini at work). **Its only data tools are `list_metrics`, `describe_metric` and `query_metrics`**, the stand-in for `DataAgentToolset.ask_data_agent` on a native BigQuery data agent. | Mirrors the work target's "ADK governed" pattern with the data agent swapped for the semantic layer: the agent code moves, only the toolset changes. Nothing custom for state, sessions or the event loop (owner, 2026-10-29). Airflow never calls the agent. |
| SL-3 | **The semantic YAML is the single source of agent context.** One generator reads `manifest.json` and `semantic_manifest.json` and writes the agent catalog the toolset reads, the warehouse comments (`persist_docs` plus a `semantic.metrics` table) and the native data agent's authored context (`system_instruction` YAML: tables, fields and aggregations, relationships from entities, glossary from metric descriptions, example queries from compiled metric SQL). The agent never reads `information_schema`. | The native agent's inputs are exactly what the manifests hold, so its context is a build artefact; BigQuery, Knowledge Catalog and the agent get the same words. |
| SL-4 | **Agents read gold, exposed and metrics only**, marked `access: public` in dbt; silver and bronze stay `protected` and out of the catalog. **Every answer carries the freshness of its metrics** from `ops.readiness` and `ops.product_deadlines` by pipeline tag; a late product is said so. | Trust is marked in dbt, not in a prompt. Freshness is a tool result the model quotes, checked by a test, never prompt logic. |
| SL-5 | **Proof is a scored eval, not a demo:** about fifteen business questions with expected numbers computed from the warehouse, through the semantic agent and through a baseline agent with one `execute_sql` tool over the same gold and exposed tables (the "ADK schema-driven" pattern), same model, both scores side by side. Live runs are opt-in and budgeted against the free tier's ~1000 requests a month; a spent quota skips with its reason, never silently. | Shows the semantic layer's value, not the model's; the baseline is what most teams run today. |

## 4. Steps

Each step is a build issue under the map; a step is done when its acceptance passes.

| Step | Issue | Delivers |
|---|---|---|
| S0 | done 2026-10-29 | The spike: pins, parity, the Python API ([research](research/semantic-layer-spike.md)) |
| S1 | [#100](https://github.com/Paradiddle131/pplk8s/issues/100) | The semantic stage in dbt: time spine, semantic models, eight metrics, `make dbt-validate`, the parity check |
| S2 | [#101](https://github.com/Paradiddle131/pplk8s/issues/101) | The catalog generator: agent catalog, warehouse comments, native authored context; public models marked |
| S3 | [#102](https://github.com/Paradiddle131/pplk8s/issues/102) | The agent on metric tools, the eval set, the text-to-SQL baseline, `make agent-eval` |
| S4 | [#103](https://github.com/Paradiddle131/pplk8s/issues/103) | Freshness in every answer; semantic validation after the finance pipeline's exposed stage |
| S5 | [#104](https://github.com/Paradiddle131/pplk8s/issues/104) | The BigQuery path: compile target, work mapping, the ten-minute demo script |

**Exit:** `make dbt-validate` and the parity check pass; `make dbt-catalog` writes the three artefacts and every gold column has a comment in the warehouse; `make agent-eval` reports the semantic agent answering every question whose metric exists, with the baseline's score beside it; a BigQuery target parses the project unchanged; the demo script runs end to end.

## 5. How this track works

- Issues hold progress; this file changes when a decision, a requirement or a step changes.
- A session that changes the repo adds a ledger fragment as the Airflow lab does (`../ledger.d/README.md`), prefixed `Semantic —`.
- Lessons for the work platform (the native data agent, BigQuery descriptions, Knowledge Catalog) go in § 6 here, one line each with evidence; the `lesson` label and `../LESSONS.md` stay the Airflow lab's.
- Risks: `dbt-metricflow` pins `dbt-core` to a minor range, so the two move together and the parity check re-runs after either moves; the model is a free tier, so every live run is opt-in.

## 6. Lessons for work

- Define each business metric once in the semantic YAML and generate descriptions, glossary and the data agent's context from the manifests; hand-written context drifts from the models (S0: one derived metric reproduced a hand-written finance table to the cent).
