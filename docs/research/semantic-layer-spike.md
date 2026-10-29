# dbt semantic layer without dbt Cloud: spike and design facts

Research for [#99](https://github.com/Paradiddle131/pplk8s/issues/99) (Map: dbt semantic layer and a metrics agent), run on 2026-10-29 (UTC) in a cloud session against the Compose warehouse.
"Measured" means run here; "stated" means read from the linked page; "unverified" means neither.

## Verdict

The semantic layer runs entirely on open-source dbt: the YAML spec is parsed by `dbt-core`, and the `dbt-metricflow` CLI and Python API validate and query it against Postgres with no dbt Cloud account (measured).
Only the hosted Semantic Layer API, its MCP tools and dbt Cloud discovery are closed (stated: the `dbt-mcp` semantic-layer tools need platform credentials).
A derived metric defined once in YAML reproduces the hand-written `exposed.net_sales_daily` to the cent (measured, below).

## Pins (measured)

| Package | Version | Note |
|---|---|---|
| `dbt-metricflow[dbt-postgres]` | 0.15.0 | requires `dbt-core<1.13,>=1.11`; extras are named after adapters (`dbt-postgres`, `dbt-bigquery`, ...), not `postgres` |
| `metricflow` | 0.213.0 | pulled by `dbt-metricflow` |
| `dbt-core` / `dbt-postgres` | 1.12.5 / 1.11.0 | the project's pins, unchanged |
| `google-adk` | 2.13.0 | `google.adk.tools.data_agent` (`DataAgentToolset`) and `google.adk.tools.bigquery` present; LiteLLM needs the `extensions` extra, `DatabaseSessionService` the `db` extra |

Host command, as the autopilot brief runs dbt on cloud:

```bash
cd dbt && DBT_HOST=localhost DBT_PORT=5433 DBT_DBNAME=dbt_dev DBT_PROFILES_DIR=$PWD \
  uvx --from "dbt-metricflow[dbt-postgres]" --with dbt-core==1.12.5 --with dbt-postgres==1.11.0 mf validate-configs
```

## The spike

On a scratch copy of `dbt/` with `dev/fixture.sql` loaded into `dbt_dev` (20 customers, 31 orders, 3 returns), `dbt build --select tag:sales tag:returns tag:finance --exclude tag:tlc` passed (58 of 58).
Added under `models/semantic/`: a daily time spine and this file.

```yaml
version: 2

semantic_models:
  - name: orders
    description: One row per order (latest version), from silver.orders.
    model: ref('slv_orders')
    defaults:
      agg_time_dimension: order_date
    entities:
      - name: order
        type: primary
        expr: order_id
      - name: customer
        type: foreign
        expr: customer_id
    dimensions:
      - name: order_date
        type: time
        type_params:
          time_granularity: day
      - name: status
        type: categorical
      - name: currency
        type: categorical
    measures:
      - name: orders_total
        description: All orders, cancelled included.
        agg: count
        expr: order_id
      - name: order_amount
        description: Order amount in EUR.
        agg: sum
        expr: amount
      - name: customers
        agg: count_distinct
        expr: customer_id

  - name: returns
    description: One row per partner return (latest version), from silver.returns.
    model: ref('slv_returns')
    defaults:
      agg_time_dimension: return_date
    entities:
      - name: return
        type: primary
        expr: return_id
      - name: order
        type: foreign
        expr: order_id
    dimensions:
      - name: return_date
        type: time
        type_params:
          time_granularity: day
      - name: reason
        type: categorical
    measures:
      - name: returns_count
        agg: count
        expr: return_id
      - name: returns_amount
        agg: sum
        expr: amount

metrics:
  - name: orders_total
    description: All orders placed, cancelled included.
    type: simple
    label: Orders
    type_params:
      measure: orders_total
  - name: orders_cancelled
    description: Orders with status cancelled.
    type: simple
    label: Cancelled orders
    type_params:
      measure: orders_total
    filter: "{{ Dimension('order__status') }} = 'cancelled'"
  - name: revenue_eur
    description: Sum of amount for non-cancelled orders (the one definition of revenue).
    type: simple
    label: Revenue (EUR)
    type_params:
      measure: order_amount
    filter: "{{ Dimension('order__status') }} <> 'cancelled'"
  - name: customers_distinct
    description: Distinct customers with at least one non-cancelled order.
    type: simple
    label: Active customers
    type_params:
      measure: customers
    filter: "{{ Dimension('order__status') }} <> 'cancelled'"
  - name: returns_eur
    description: Sum of partner return amounts.
    type: simple
    label: Returns (EUR)
    type_params:
      measure:
        name: returns_amount
        fill_nulls_with: 0
  - name: returns_count
    description: Number of partner returns.
    type: simple
    label: Returns
    type_params:
      measure: returns_count
  - name: net_revenue_eur
    description: Revenue minus partner returns (finance's net sales).
    type: derived
    label: Net revenue (EUR)
    type_params:
      expr: revenue_eur - returns_eur
      metrics:
        - name: revenue_eur
        - name: returns_eur
  - name: cancellation_rate
    description: Share of orders cancelled.
    type: ratio
    label: Cancellation rate
    type_params:
      numerator: orders_cancelled
      denominator: orders_total
```

Time spine (`metricflow_time_spine.sql`, `materialized: table`; the YAML sets `time_spine.standard_granularity_column: date_day` and `granularity: day` on the column):

```sql
-- dialect: generate_series is Postgres; BigQuery uses GENERATE_DATE_ARRAY.
select cast(d as date) as date_day
from generate_series(date '2024-01-01', date '2027-12-31', interval '1 day') as d
```

Results (measured):

- `dbt parse` writes `target/semantic_manifest.json` with 2 semantic models and 8 metrics.
- `mf validate-configs`: entities, measures and metrics validated against the warehouse, 0 errors.
- `mf list metrics` shows each metric with its dimensions (`metric_time`, `order__status`, `order__currency`, `return__reason`, ...).
- `mf query --metrics revenue_eur,returns_eur,net_revenue_eur --group-by metric_time__day`:

| day | revenue_eur | returns_eur | net_revenue_eur | `exposed.net_sales_daily` |
|---|---|---|---|---|
| 2026-10-01 | 981.69 | 17.50 | 964.19 | 981.69 / 17.50 / 964.19 |
| 2026-10-02 | 868.65 | 7.25 | 861.40 | 868.65 / 7.25 / 861.40 |

- `mf query --metrics orders_total,orders_cancelled,customers_distinct,cancellation_rate --group-by metric_time__day` matches `gold.daily_sales` (15 / 2 / 9 and 15 / 3 / 9).
- `--where "{{ Dimension('order__currency') }} = 'EUR'"` and `--explain` (the compiled SQL) work; `--csv` writes a file.
- Python API: `CLIConfiguration().setup()` gives an engine in about 1 s; `MetricFlowQueryRequest.create(metric_names=..., group_by_names=..., where_constraints=...)` then `engine.query(req).result_df` answers in under 0.1 s and `engine.explain(req).sql_statement.sql` returns the SQL.

Two things that bit:

- `fill_nulls_with` belongs on the simple metric's `type_params.measure`, not on a derived metric's input list (parse error otherwise).
- `join_to_timespine: true` on the returns metric made the derived metric emit one row per spine day; without it the derived metric joins the two metrics with a full outer join on `metric_time` and shows only days with data.

## Native patterns (stated, Google docs 2026-10)

The Conversational Analytics API's [integration patterns](https://docs.cloud.google.com/gemini/data-agents/conversational-analytics-api/integration-patterns) page names ten; the ones that shape the lab:

| Pattern | What runs | Lab stand-in |
|---|---|---|
| 6 ADK schema-driven | `BigQueryToolset.ask_data_insights` with inline table references; SQL from schema inference, no semantic guardrails | the eval baseline: an ADK agent with one `execute_sql` tool over gold and exposed |
| 7 ADK governed | `DataAgentToolset.ask_data_agent` on a pre-configured data agent (knowledge sources, descriptions, instructions, verified queries, glossary) | the semantic agent: the same ADK agent with a MetricFlow-backed toolset in the data agent's place |
| 9 MCP | MCP Toolbox `bigquery-conversational-analytics` wrapping `chat`; ADK connects through `McpToolset` | not built; the ADK toolset seam covers it |

[BigQuery data agents](https://docs.cloud.google.com/bigquery/docs/conversational-analytics) take custom table and field metadata, instructions, verified queries (formerly golden queries) and glossary terms (BigQuery custom glossary or Knowledge Catalog), in that priority; they advise curated views over agent-chosen joins, at most 100 knowledge sources and about 20 per agent in practice.
The authored context for BigQuery ([page](https://docs.cloud.google.com/gemini/docs/conversational-analytics-api/data-agent-authored-context-bq)) is a `system_instruction` YAML with `tables[].table.{name, fields[].field.{name, aggregations}}`, `relationships[].relationship.{name, description, relationship_type, join_type, left_table, right_table, relationship_columns[].{left_column, right_column}}`, `glossaries[].glossary.{term, description, synonyms}` and `additional_descriptions[].text`; table and column `description`, `synonyms`, `tags` and `example_queries` (`naturalLanguageQuestion`, `sqlQuery`, `parameters`) are structured fields set beside it; `stagingContext` and `publishedContext` version it.
`DataAgentToolset` ([ADK docs](https://adk-labs.github.io/adk-docs/integrations/data-agent), ADK ≥ 1.23) exposes `list_accessible_data_agents`, `get_data_agent_info` and `ask_data_agent`, takes a `DataAgentCredentialsConfig` and a `DataAgentToolConfig` (`location`, `max_query_result_rows`), and references the agent as `projects/{project}/locations/{location}/dataAgents/{agent}`.

What this means for the design: every input of a native data agent (descriptions, relationships, glossary, verified queries) can be generated from the dbt manifests, so the semantic YAML is the single source and the native agent's context is a build artefact, not hand-written text.

## Options weighed

- **Semantic layer engine:** MetricFlow (chosen: the dbt spec, runs on the project's pins, BigQuery and Postgres adapters); Cube or the Boring Semantic Layer would add a second model of the data beside dbt; LookML needs Looker.
- **Agent plumbing:** ADK (chosen: the framework behind Gemini Enterprise and the native toolsets; runner, sessions, eval and `api_server` come with it); a bespoke loop would re-create what bq-agent-lab already retired.
- **Where the agent lives:** pplk8s `services/semantic-agent/` (owner's pick: one demo repo, a Cloud Run stand-in like EL Factory); a new repo would duplicate the warehouse; bq-agent-lab is frozen.
- **Model:** OpenRouter's free tier behind a `MODEL_BACKEND` seam (about 1000 requests a month: every live eval is opt-in and budgeted); Gemini at work.

## Unverified

- `dbt compile` on a `dbt-bigquery` target without a warehouse (S5 settles it; `dbt parse` works offline for certain).
- The exact `ask_data_agent` tool arguments (the ADK page does not list them); the lab toolset's contract is `question` in, text plus rows plus SQL out, which is what the docs describe.
