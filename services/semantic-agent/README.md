# Semantic agent

An ADK agent that answers business questions through the dbt semantic layer's metrics instead of writing SQL, and the text-to-SQL baseline it is scored against ([`semantic/PLAN.md`](../../semantic/PLAN.md) SL-2, SL-5).
It stands in for a Cloud Run service; at work the metric toolset is the seam a native BigQuery data agent fills (`DataAgentToolset.ask_data_agent`).

**One agent is deployed: `semantic_agent`.**
`sql_baseline` is the eval's control, not a second production agent: `make agent-eval` runs it in-process beside the semantic agent to measure what the semantic layer adds, and `make agent-web` shows it locally for the demo's comparison; the image, the Deployment and its Secret leave it out (#163).

## The two packages

| Package | Tools | Reads |
|---|---|---|
| `semantic_agent` | `list_metrics`, `describe_metric`, `query_metrics` | S2's catalog (`dbt/target/catalog/agent.json`) and MetricFlow's Python API on the dbt project, as the read-only `agent_metrics` role (silver and semantic, plus `ops.readiness` and `ops.product_deadlines` for freshness) |
| `sql_baseline` (eval only) | `execute_sql` | gold and exposed only, as the read-only `agent_sql` role, one statement per call (10 s statement timeout); the "ADK schema-driven" pattern: the catalog's public models as table names in the instruction (read from `agent.json` like the semantic agent's metrics, so the two never see different tables), columns from `information_schema` |

`query_metrics` never takes SQL.
It takes metric names, group-bys (`metric_time__day`, `__week`, `__month`, ...; `order__status`), filters as `{dimension, operator, values}` on categorical dimensions, a date range and an order.
Each part is checked against the catalog; the filter becomes a MetricFlow `{{ Dimension(...) }}` condition with every value a quoted literal.
MetricFlow renders that condition as a Jinja template before it compiles SQL, so a value holding `{{`, `{%` or `{#` is refused (`'{{ 7*7 }}'` would otherwise filter on `'49'`, #161).
A categorical dimension whose column declares its values (an `accepted_values` test, which the catalog carries as `values`) shows them in `describe_metric`, and a filter value outside them comes back as an error naming them: a guessed value ("damaged goods" for `damaged`) would match no row and read as a confident zero.
A request the semantic layer cannot answer (an unknown metric, a dimension the metric lacks) comes back as `{"error": ...}` for the model to read.

`list_metrics` also returns the dbt saved queries (`dbt/models/semantic/saved_queries.yml`, #164): the recurring questions, each with its fixed metrics, group-bys and filters.
`query_metrics(saved_query=...)` runs one by name, narrowed by the call's dates, filters, order and limit (MetricFlow refuses other metrics or group-bys beside a saved query); the result names the saved query's metrics, which its freshness, the audit row and the eval's `metric_choice` use.

The roles, their grants and the audit table come from the dbt macro `agent_warehouse` (`make agent-warehouse`), which `make services-up` runs on `warehouse` and `make agent-eval` on `dbt_dev`.
The database, not the prompt, keeps each agent in its tables (SL-4).

## Audit

Every call to a data tool (`query_metrics`, `execute_sql`, or whatever replaces them), answered or refused, writes one row to `ops.agent_queries` (SL-10): the agent, user, session, invocation and call id; the metrics, filters and other arguments as the model sent them; the SQL (the model's, or the one MetricFlow compiled); the rows returned; the freshness statement; the error.
`guard.py` builds both agents' ADK `after_tool_callback` and `audit.py` writes the row, so the tools themselves stay unchanged.
A data tool is every tool but the ones the toolset seam names as reading only the catalog (`tools.CATALOG_TOOLS`: listing and describing metrics), so the audit survives a swap to `DataAgentToolset`, whose data tool is `ask_data_agent` (#177); a catalog tool the swap forgets to name is audited, not a data tool skipped.
- The row is written as `agent_audit`, a role that may only insert into that table: it cannot read, change or delete a row, or write anywhere else.
- The agents' own roles write nothing, the audit included: the baseline runs whatever single statement its model writes, and the transaction mode is only one guard (before the tool refused a second statement, `commit; begin read write` left it), so a role's privileges keep the audit unforged.
- An audit row that cannot be written withholds the result: the model gets an error naming the reason instead of rows.

The writer reads `AUDIT_URL`, else the `DBT_*` host, port and database with the `agent_audit` login, so the audit lands in the warehouse the query read.

## Freshness

Every answered data call's result carries a `freshness` field (SL-4, S4): the after-tool callback (`guard.py`), not the toolset, attaches it for the metrics the result names (`query_metrics` names the ones it ran, a saved query's included), else the ones the call asked for, and `freshness.py` builds it:
- The catalog names the readiness products each metric reads, `<pipeline>.<layer>` of its models (`sales.silver`).
- A product is ready up to the end of its newest `ready` interval in `ops.readiness`.
- It is late by the lab's D37 rule: that end is older than its deadline in `ops.product_deadlines`, or it has a deadline and no ready interval.
- A layer with no deadline of its own takes its pipeline's (`sales.silver` takes `sales`, 36 h); one with neither is never late.

The field holds each product's facts and one `statement` ("Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.").
The instruction tells the model to quote that statement word for word; no freshness rule is in the prompt.
An unreadable ledger is said in the statement ("Freshness unknown: ..."), never raised, and so is a result that names no metrics, as `ask_data_agent`'s may not.
A refused call (`{"error": ...}`) gets no freshness.

## Run with only the dbt project and a warehouse

The agent needs no Airflow, no readiness ledger and no Compose stand-in: a Postgres database the dbt project builds in, and a model key (#166).
Everything it needs in the warehouse beside the models comes from one dbt macro, `agent_warehouse` (`dbt/macros/agent_warehouse.sql`): the `agent_metrics`, `agent_sql` and `agent_audit` roles, their grants and `ops.agent_queries`.

```bash
make agent-warehouse DBT_DBNAME=mydb      # dbt run-operation agent_warehouse; idempotent
# build the models into mydb, e.g. dbt build --select tag:sales tag:returns tag:finance tag:marketing
make dbt-catalog DBT_DBNAME=mydb
cd services/semantic-agent && DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=mydb DBT_USER=agent_metrics DBT_PASSWORD=agent_metrics \
  uv run adk web src                      # in-memory sessions without --session_service_uri
```

Run `make agent-warehouse` again after a schema is dropped and rebuilt, or after the readiness ledger appears, so the roles get their grants back.
Without the ledger every answer says "Freshness unknown: the readiness ledger could not be read (...)", and every data query still leaves its audit row.
`make agent-standalone-check` (`tests/e2e/agent-standalone-check.sh`) proves it on an empty database with one scripted turn: 861.4 through `query_metrics`, its audit row, "Freshness unknown".
On BigQuery the same macro creates `ops.agent_queries` (checked on the emulator by `make bigquery-emulator-check`); the roles there are IAM, one service account per deployed agent.

## Model

`model.py` is the only place that names a provider: `MODEL_BACKEND` (`openrouter`, the lab default, or `gemini`) and `MODEL_ID` (default `nvidia/nemotron-3.5-super-vl:free`; on OpenRouter only a free model, an id ending `:free`, builds), bounded by `MODEL_TIMEOUT_S` (120) and `MODEL_RETRIES` (2).
The OpenRouter key is `OPENROUTER_API_KEY`; on cloud the environment's network secret injects it, so the variable only needs a placeholder.

A model call that still fails after its retries ends the turn with an answer, not an exception: both agents set ADK's `on_model_error_callback` to `answer_model_failure`.
- A spent daily quota (OpenRouter's `free-models-per-day`, Gemini's `PerDay` quota) answers "No answer: the model's daily request quota is spent." with the reset time.
- A per-minute or upstream limit answers "No answer: the model is rate-limited right now; ask again in 34 s."
- Any other failure names the provider's message.

LiteLLM's retries back off for a few seconds and ignore `Retry-After`, so nothing waits for a reset.
The event carries the failure in `custom_metadata["model_failure"]`.

## Run

```bash
make services-up
make dbt-catalog DBT_DBNAME=dbt_dev   # or warehouse
make agent-serve AGENT_DBNAME=dbt_dev
```

`agent-serve` runs `adk api_server` on `localhost:8000` with both packages (the baseline for local comparison only), sessions in the `agent_sessions` database of the metadata DB (ADK's `DatabaseSessionService`; `make services-up` creates it).

## Deploy

`make workloads-up` builds the image (`Dockerfile`, tagged `AGENT_IMAGE` in the Makefile), pushes it to the local registry and deploys it in the kind cluster's `workloads` namespace beside EL Factory: the Cloud Run stand-in of SL-2 (`platform/k8s/workloads/semantic-agent-*.yaml`).
- The image holds the semantic agent alone (`/app/agents/semantic_agent`, what `adk api_server` serves on 8080) and the dbt project; the build parses it once as a smoke check.
- An initContainer runs `dbt parse` and `build_catalog.py` at pod start, for the database the pod reads (`AGENT_DBNAME`, default `warehouse`): MetricFlow's compiled SQL names that database.
- The Secret `semantic-agent-credentials` (written by `workloads-up.sh`) carries the `agent_metrics` and `agent_audit` logins (no `agent_sql`: the baseline is never deployed), the session store (`agent_sessions` on the metadata DB) and `OPENROUTER_API_KEY`.
- `EGRESS_PROXY` and `EGRESS_CA` route the model calls through a TLS-intercepting proxy (the cloud sandbox); unset elsewhere.

`make agent-deploy-check` (`tests/e2e/agent-deploy-check.sh`) is the live check: it builds the fixture in `dbt_dev`, deploys with `AGENT_DBNAME=dbt_dev`, asks "What was net revenue on 2 October 2026?" through a port-forwarded Service and asserts the Service lists `semantic_agent` alone and answers 861.4 through `query_metrics`, the session's events in `agent_sessions` and its audit row in `ops.agent_queries` (one model turn).
`uv run adk web src` from this folder is the demo surface.

## Checks

| Command | What it proves | Model |
|---|---|---|
| `make agent-test` (in `make test`) | the tools, the request checks, freshness (fresh, late, no ready row), the agent loop through ADK's `Runner`, the audit row of each data query (and a result withheld when it cannot be written), the audit and freshness kept for a stand-in `DataAgentToolset` whose data tool has another name, the eval driver, a spent quota and a refused key through the real LiteLLM client against a local 429 or 401 server; with `make services-up`, the ledger read as `agent_metrics`, the baseline's role (no `ops`, no `silver`, no writes, the timeout), the audit writer limited to inserting audit rows, no agent role writing the audit even in a read-write transaction and sessions surviving a new session service on Postgres | scripted; no test reaches a live model (`OPENROUTER_API_BASE` points at a closed local port) |
| `make agent-eval` | the scored eval below | live, ~2 x 15 turns |

`make agent-eval` (`tests/e2e/agent-eval.sh`) builds `dev/fixture.sql` in `dbt_dev`, writes the catalog, grants the roles, records the fixture's days in `ops.readiness`, and runs `python -m semantic_agent.evaluation`.
Each question of `evals/questions.yaml` gets its expected number from the warehouse at run time, then goes once through each agent on ADK's `LocalEvalService`, scored by three custom metrics declared in `evals/eval_config.json`:
- `answer_correct`: the answer carries the warehouse's number, or, for the semantic agent on a question no metric covers, says so; numbers inside a quoted freshness statement do not count.
- `metric_choice`: the semantic agent queried the expected metrics.
- `freshness_quoted`: the semantic agent's answer quotes every freshness statement its queries returned.

The scores go to stdout and [`docs/research/semantic-agent-eval.md`](../../docs/research/semantic-agent-eval.md); question ids as arguments run only those and write no report.
A failed model call is reported per question with its answer, never dropped.
A rate-limited question waits out the limit once (at most 90 s) and runs again.
Once the daily quota is spent, the questions left are skipped with that reason and never sent, the baseline included; the run prints what it got, leaves the report as it was and exits 3.
A refused key (401 or 403) does the same, and so does a run where no question got an answer; `agent-eval.sh` asks OpenRouter's `/key` endpoint about the key before the build, which spends no model request.
Every agent sends its `MODEL_RETRIES` with each request (`request_config()`), since ADK's eval engine otherwise gives the request its own 7 attempts.
