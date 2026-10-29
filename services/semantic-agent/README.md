# Semantic agent

An ADK agent that answers business questions through the dbt semantic layer's metrics instead of writing SQL, and the text-to-SQL baseline it is scored against ([`semantic/PLAN.md`](../../semantic/PLAN.md) SL-2, SL-5).
It stands in for a Cloud Run service; at work the metric toolset is the seam a native BigQuery data agent fills (`DataAgentToolset.ask_data_agent`).

## The two agents

| Package | Tools | Reads |
|---|---|---|
| `semantic_agent` | `list_metrics`, `describe_metric`, `query_metrics` | S2's catalog (`dbt/target/catalog/agent.json`) and MetricFlow's Python API on the dbt project, as the read-only `agent_metrics` role (silver and semantic) |
| `sql_baseline` | `execute_sql` | gold and exposed only, as the read-only `agent_sql` role (10 s statement timeout); the "ADK schema-driven" pattern: table names in the instruction, columns from `information_schema` |

`query_metrics` never takes SQL.
It takes metric names, group-bys (`metric_time__day`, `__week`, `__month`, ...; `order__status`), filters as `{dimension, operator, values}` on categorical dimensions, a date range and an order.
Each part is checked against the catalog; the filter becomes a MetricFlow `{{ Dimension(...) }}` condition with every value a quoted literal.
A request the semantic layer cannot answer (an unknown metric, a dimension the metric lacks) comes back as `{"error": ...}` for the model to read.

The roles live in `platform/compose/warehouse-init/02-agent-roles.sql`, which `make services-up` applies to `warehouse` and `make agent-eval` to `dbt_dev`.
The database, not the prompt, keeps each agent in its tables (SL-4).

## Model

`model.py` is the only place that names a provider: `MODEL_BACKEND` (`openrouter`, the lab default, or `gemini`) and `MODEL_ID` (default `nvidia/nemotron-3.5-super-vl:free`), bounded by `MODEL_TIMEOUT_S` (120) and `MODEL_RETRIES` (2).
The OpenRouter key is `OPENROUTER_API_KEY`; on cloud the environment's network secret injects it, so the variable only needs a placeholder.

## Run

```bash
make services-up
make dbt-catalog DBT_DBNAME=dbt_dev   # or warehouse
make agent-serve AGENT_DBNAME=dbt_dev
```

`agent-serve` runs `adk api_server` on `localhost:8000` with both agents, sessions in the `agent_sessions` database of the metadata DB (ADK's `DatabaseSessionService`; `make services-up` creates it).
`uv run adk web src` from this folder is the demo surface.

## Checks

| Command | What it proves | Model |
|---|---|---|
| `make agent-test` (in `make test`) | the tools, the request checks, the agent loop through ADK's `Runner`, the eval driver; with `make services-up`, the baseline's role (no `ops`, no `silver`, no writes, the timeout) and sessions surviving a new session service on Postgres | scripted |
| `make agent-eval` | the scored eval below | live, ~2 x 15 turns |

`make agent-eval` (`tests/e2e/agent-eval.sh`) builds `dev/fixture.sql` in `dbt_dev`, writes the catalog, grants the roles, and runs `python -m semantic_agent.evaluation`.
Each question of `evals/questions.yaml` gets its expected number from the warehouse at run time, then goes once through each agent on ADK's `LocalEvalService`, scored by two custom metrics declared in `evals/eval_config.json`:
`answer_correct` (the answer carries the warehouse's number, or, for the semantic agent on a question no metric covers, says so) and `metric_choice` (the semantic agent queried the expected metrics).
The scores go to stdout and [`docs/research/semantic-agent-eval.md`](../../docs/research/semantic-agent-eval.md); question ids as arguments run only those and write no report.
A failed model call (a spent free-tier quota included) is reported per question with the provider's message, never dropped.
