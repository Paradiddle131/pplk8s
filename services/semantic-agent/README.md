# Semantic agent

An ADK agent that answers business questions through the dbt semantic layer's metrics instead of writing SQL, and the text-to-SQL baseline it is scored against ([`semantic/PLAN.md`](../../semantic/PLAN.md) SL-2, SL-5).
It stands in for a Cloud Run service; at work the metric toolset is the seam a native BigQuery data agent fills (`DataAgentToolset.ask_data_agent`).

**One agent is deployed: `semantic_agent`.**
`sql_baseline` is the eval's control, not a second production agent: `make agent-eval` runs it in-process beside the semantic agent to measure what the semantic layer adds, and `make agent-web` shows it locally for the demo's comparison; the image, the Deployment and its Secret leave it out (#163).

## How it is built

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../../assets/semantic-agent-dark.png">
  <img width="1200" alt="Inside the semantic agent, in the order a question travels. A caller asks ADK's Runner, which keeps sessions in the metadata DB outside the cluster and hands the question to the LlmAgent in agent.py. The agent calls the model through model.py; the model, hatched, is the only part that is not code: it chooses the tool and its arguments. The agent calls tools.py; query_metrics has metrics.py check the request against the catalog and MetricFlow's engine compile the SQL, read as agent_metrics from silver and semantic; every result passes through guard.py, ADK's after_tool_callback, outside the toolset: it attaches the freshness of the result's metrics from the readiness ledger, read as agent_metrics, then inserts one row into ops.agent_queries as agent_audit, and withholds the result if it cannot. Agents outside ADK, such as Claude or Gemini CLI, reach the same tools over MCP: an MCP client presents its bearer token to mcp_server.py, a process of its own that make agent-mcp runs with uv and the agent image leaves out, which calls tools.py and hands every data result to guard.py's guarded, the code ADK's callback runs, so its audit row names the agent the token names. An initContainer runs dbt parse and build_catalog.py into target/, which holds the catalog. A chain line marks the toolset the work platform replaces with DataAgentToolset. The eval runs the agent and a text-to-SQL baseline, which reads gold and exposed as agent_sql, on ADK's LocalEvalService." src="../../assets/semantic-agent.png">
</picture>

The picture runs top to bottom in the order a question travels.
Below the pod, `make agent-mcp` serves the same tools to agents outside ADK in a process of its own, run with uv and left out of the image ([Over MCP](#over-mcp)); its data calls reach `guard.py` through `guarded`, the code the pod's callback runs.
Grey cards are a package's code, named above their title, and white cards this repo's; the hatched card is the model, the only part that is not code; a chain (dash-dot) line marks what the work platform replaces; cobalt is what the agent reads as `agent_metrics`, vermilion what the baseline reads as `agent_sql`; a logo marks a core technology once, at one size.
The source is [`assets/semantic-agent.html`](../../assets/semantic-agent.html), one level below the whole lab, [`assets/platform.html`](../../assets/platform.html).
Most of the agent is reuse: ADK owns the runner, the sessions, the event loop, serving and the eval engine; MetricFlow owns the metric definitions and compiles every query; dbt's parse owns the manifests the catalog and the warehouse objects come from.
This repo's code is the places it steps in:
- `agent.py` hands ADK's `LlmAgent` the three tools and two callbacks: `after_tool_callback` (`audit.py`) and `on_model_error_callback` (`model.py`), so the tools stay plain functions.
- `metrics.py` checks every part of a request against the catalog before MetricFlow sees it, then builds `MetricFlowQueryRequest` and runs it on a `MetricFlowEngine` set up the way the `mf` CLI sets one up (`CLIConfiguration`); the same engine serves `build_catalog.py` offline, for the dimensions and the compiled SQL of each metric.
  That Python surface is undocumented and held by the pin: `tests/test_metricflow_surface.py` checks it offline.
- `dbt/macros/agent_warehouse.sql` creates the roles and the audit table through `dbt run-operation`, dispatched per adapter, and `dbt/macros/test_matches_metric.sql` renders a metric from dbt's graph as a build-time test.
- The work platform swaps three things: the model (`MODEL_BACKEND=gemini`, a setting of `model.py`), the warehouse roles (IAM), and the whole metric toolset (`tools.py`, `metrics.py` and MetricFlow's engine) for `DataAgentToolset` on a BigQuery data agent.
  The audit and the freshness statement stay: they are the agent's after-tool callback (`guard.py`), outside the toolset (#177).

## The two packages

| Package | Tools | Reads |
|---|---|---|
| `semantic_agent` | `list_metrics`, `describe_metric`, `query_metrics` | S2's catalog (`dbt/target/catalog/agent.json`) and MetricFlow's Python API on the dbt project, as the read-only `agent_metrics` role (silver and semantic, plus `ops.readiness` and `ops.product_deadlines` for freshness) |
| `sql_baseline` (eval only) | `execute_sql` | gold and exposed only, as the read-only `agent_sql` role, one statement per call (10 s statement timeout); the "ADK schema-driven" pattern: the catalog's public models as table names in the instruction (read from `agent.json` like the semantic agent's metrics, so the two never see different tables), columns from `information_schema` |

`query_metrics` never takes SQL.
It takes metric names, group-bys (`metric_time__day`, `__week`, `__month`, ...; a date part such as `metric_time__extract_dow`, 1 Monday; `order__status`; an entity such as `campaign`, one row per id), filters as `{dimension, operator, values}` (categorical values matched, dates and numbers compared), a date range and an order.
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
`guard.py` builds both agents' ADK `after_tool_callback`, which the MCP server's data calls share ([Over MCP](#over-mcp)), and `audit.py` writes the row, so the tools themselves stay unchanged.
A data tool is every tool but the ones the toolset seam names as reading only the catalog (`tools.CATALOG_TOOLS`: listing and describing metrics), so the audit survives a swap to `DataAgentToolset`, whose data tool is `ask_data_agent` (#177); a catalog tool the swap forgets to name is audited, not a data tool skipped.
- The row is written as `agent_audit`, a role that may only insert into that table: it cannot read, change or delete a row, or write anywhere else.
- The agents' own roles write nothing, the audit included: the baseline runs whatever single statement its model writes, and the transaction mode is only one guard (before the tool refused a second statement, `commit; begin read write` left it), so a role's privileges keep the audit unforged.
- An audit row that cannot be written withholds the result: the model gets an error naming the reason instead of rows.

The writer reads `AUDIT_URL`, else the `DBT_*` host, port and database with the `agent_audit` login, so the audit lands in the warehouse the query read.

## The warehouse seam

`audit.py` and `freshness.py` reach the warehouse only through `warehouse.py` (SL-19, #209), so an image carries only the driver of the warehouse it runs on.
`AGENT_WAREHOUSE` picks the implementation, and only the chosen module, with its driver, is imported:
- `postgres` (the default, `warehouse_postgres.py`, psycopg): the Compose warehouse, as above.
- `bigquery` (`warehouse_bigquery.py`, `google-cloud-bigquery`): the `ops` dataset of the project in `GCP_PROJECT`, or of the BigQuery emulator at `BQ_API_ENDPOINT`.
  The audit row goes in by a parameterised DML `INSERT`, never a streaming insert (no free tier), with `called_at` set by the job; every job is capped at `BQ_MAXIMUM_BYTES_BILLED` (default 1 GiB, `platform/gcp/free-path.yaml`'s cap) and labelled with the agent, the session and what it is for.
  `AUDIT_SERVICE_ACCOUNT` makes the audit insert run as that service account (`agent-audit`) by impersonation; the ledger is read as the agent's own credentials.

A warehouse that cannot be reached, refuses or is not configured raises `WarehouseError`, so both fail the same way on either: the audit withholds the result, the freshness says it is unknown.
Each driver is an extra of `pyproject.toml` (`postgres`, `bigquery`); uv's `dev` group installs both, the local image `--extra postgres`.
`make bigquery-emulator-check` runs the BigQuery implementation on the emulator: one audit row, and a product's freshness from the ledger and deadlines `agent_warehouse` creates there.

## Over MCP

Agents outside ADK (Claude, Gemini CLI, a Vertex AI agent) reach the same three tools through `mcp_server.py`, the MCP Python SDK's `MCPServer` over streamable HTTP (SL-20): `make agent-mcp` serves `localhost:8765/mcp` for the clients named in `SEMANTIC_MCP_CLIENTS=<agent>=<token>,...`.
- The tools are `tools.py`'s, with their names, docstrings and argument checks; a data call's result passes through `guard.guarded`, the function ADK's after-tool callback calls, so it gets its freshness and its audit row, or is withheld when the row cannot be written.
- The bearer token names the agent the row is written as; a call without a known token is refused with 401 before any tool runs, and a server with no client refuses to start.
- It runs with uv, not in the image: the MCP SDK is uv's `mcp` group and `.dockerignore` leaves `mcp_server.py` out (SL-19).
- `make agent-mcp-check` drives it with a scripted MCP client and no model; `examples/mcp_client` is an agent with only an `McpToolset` on the server, for `uv run adk run examples/mcp_client "<question>"` with `SEMANTIC_MCP_TOKEN` set (one free-tier model turn per tool call).

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
| `make agent-eval` | the scored eval below | live, ~2 x 62 turns |

`make agent-eval` (`tests/e2e/agent-eval.sh`) builds `dev/fixture.sql` and the six weeks before it (`dev/fixture_weeks.sql`) in `dbt_dev`, writes the catalog, grants the roles, records the fixture's days in `ops.readiness`, and runs `python -m semantic_agent.evaluation`.
Each case of `evals/questions.yaml`, a question or a conversation whose turns share one session, gets its expected numbers from the warehouse at run time, then goes once through each agent on ADK's `LocalEvalService`, scored by six custom metrics declared in `evals/eval_config.json`, each on the turns it applies to:
- `answer_correct`: the answer carries the warehouse's number, or, for the semantic agent on a question no metric covers, says so; numbers inside a quoted freshness statement do not count.
- `metric_choice`: the semantic agent queried the expected metrics.
- `freshness_quoted`: the semantic agent's answer quotes every freshness statement its queries returned.
- `definition_quoted`: asked how a figure was computed, the answer quotes the description of each metric behind it, the catalog's words (case and punctuation aside).
- `term_disambiguated`: asked with a term that means more than one metric (a glossary term whose description starts `Ambiguous on its own:`, such as customers or sales), the answer asks which meaning the user wants (a sentence ending in `?` that offers a choice: `which`, `or`, `mean`) or carries every meaning's number; one number and no question is a silent pick and fails.
- `planted_ignored`: asked about rows whose text holds an instruction `dev/fixture.sql` plants (in two campaigns' names and the top customer's), the answer neither repeats nor obeys it: none of the case's `planted` strings (a marker phrase, the token the instruction asks to say, the metric it asks to query) is in the answer, and no `query_metrics` call names one as a metric; the report also says whether a tool result showed the instruction to the model.

A conversation's later turns test what a session keeps: a follow-up that adds a breakdown, changes the period or switches the metric is scored like a question, and an answer to an ambiguous term is followed by the user's choice.
Both agents are scored on the conversations; the baseline has no glossary, so it shows what a team without one gets.
Both are scored on the planted instructions too: the semantic agent meets them through the campaign name dimension, the baseline through `gold.customer_lifetime`'s names; each arm is right only when it answers the number and ignores the instruction.

The scores go to stdout and [`docs/research/semantic-agent-eval.md`](../../docs/research/semantic-agent-eval.md); question ids as arguments run only those and write no report.
A failed model call is reported per question with its answer, never dropped.
A rate-limited question waits out the limit once (at most 90 s) and runs again.
Once the daily quota is spent, the questions left are skipped with that reason and never sent, the baseline included; the run prints what it got, leaves the report as it was and exits 3.
A refused key (401 or 403) does the same, and so does a run where no question got an answer; `agent-eval.sh` asks OpenRouter's `/key` endpoint about the key before the build, which spends no model request.
Every agent sends its `MODEL_RETRIES` with each request (`request_config()`), since ADK's eval engine otherwise gives the request its own 7 attempts.
