# Ten-minute demo: a semantic layer an agent answers through

A screen-share script for a team whose data lands in BigQuery, whose agents guess which table to trust, and who will not run dbt Cloud ([`semantic/PLAN.md`](../semantic/PLAN.md) § 1).
It runs on the dev fixture (`dbt/dev/fixture.sql`, the `dbt_dev` database), so every number below is fixed and the script can be rehearsed in one sitting.
Every command is a `make` target from the repository root.

## Before the call (about 5 minutes, once)

```bash
make services-up
make agent-eval
make semantic-check
make bigquery-check
```

- `agent-eval` does the setup for the rest of the demo, then runs the live eval (about 90 free-tier model requests):
  - it builds the fixture's sales, returns and finance models in `dbt_dev`;
  - it writes the catalog;
  - it grants the agents' read-only roles;
  - it records the fixture's days in `ops.readiness`.
  It ends with `written to …/docs/research/semantic-agent-eval.md`; exit 3 means the model's daily quota ran out, and the last report stays.
- `semantic-check` ends `ok: the eight metrics equal gold.daily_sales and exposed.net_sales_daily on 2 days`.
- `bigquery-check` ends `ok: build_catalog and check_catalog pass on the bigquery target`.

## The script

**1. One definition (1 min).**
Open `dbt/models/semantic/semantic.yml` at `net_revenue_eur`: `revenue_eur - returns_eur`, a derived metric over two semantic models.
Say: revenue, orders, returns and net revenue each have exactly one definition, here, in the open-source dbt project.

**2. It is checked (1 min).**

```bash
make dbt-validate DBT_DBNAME=dbt_dev
```

Expect five `Successfully validated … against data warehouse (ERRORS: 0 …)` lines: semantic models, dimensions, entities, measures, metrics.
In Airflow the same check runs after `finance_daily`'s exposed build (`validate_semantic_layer`).

**3. Query a metric, not a table (1 min).**

```bash
make metric-query DBT_DBNAME=dbt_dev
```

Expect:

| metric_time__day | revenue_eur | returns_eur | net_revenue_eur |
|---|---|---|---|
| 2026-10-01 | 981.69 | 17.5 | 964.19 |
| 2026-10-02 | 868.65 | 7.25 | 861.4 |

Say: `exposed.net_sales_daily`, the hand-written finance table, holds the same numbers to the cent; `semantic-check` asserts it.

**4. The same words everywhere (1.5 min).**

```bash
make warehouse-sql DBT_DBNAME=dbt_dev SQL='\d+ gold.daily_sales'
make warehouse-sql DBT_DBNAME=dbt_dev SQL='select metric_name, label, description from semantic.metrics'
```

Expect a description on every column (`revenue_eur | Sum of amount for non-cancelled orders.`) and eight metrics.
Then open `dbt/target/catalog/data_agent/system_instruction.yaml`: the BigQuery data agent's authored context (tables, aggregations, relationships, glossary), generated from the same YAML.

**5. On BigQuery (1 min).**
Open `dbt/target/bigquery/catalog/data_agent/example_queries.json`: one verified query per metric, compiled by MetricFlow for BigQuery (`` FROM `pplk8s-lab`.`silver`.`orders` ``), with no GCP account.
Say: the descriptions, the glossary and the verified queries are build artefacts; nothing in the data agent's context is hand-written ([mapping](semantic-layer-on-bigquery.md)).

**6. Ask the agent (2.5 min).**

```bash
make agent-web AGENT_DBNAME=dbt_dev
```

Open `http://localhost:8000`, pick `semantic_agent`, and ask:
- "What was net revenue on 1 October 2026, after partner returns?"
  The answer is €964.19, then its freshness: "Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline."
  The events panel shows `list_metrics`, `describe_metric`, then `query_metrics`.
- "How many orders have shipped?"
  The answer is 11: `orders_total` filtered on `order__status = shipped`.
  Switch to `sql_baseline` and ask again: it has said 25 (orders minus cancellations), a confident wrong number from a table without the breakdown.
- "What was our revenue from customers in Germany on 1 October 2026?"
  The semantic agent says the semantic layer has no metric by country, rather than guessing.

The model is a free OpenRouter model; an answer takes 5 to 30 seconds, and a spent quota answers "No answer: the model's daily request quota is spent." instead of failing.

**7. The score (1 min).**
Open [`docs/research/semantic-agent-eval.md`](research/semantic-agent-eval.md): fifteen questions, the same model, both agents.
As of the last run, the semantic agent was right on all 15 and quoted its freshness in all 13 metric answers; the text-to-SQL baseline was right on 12.

## If something goes wrong

- A model answer that is slow or rate-limited: wait a minute and ask again; the eval's numbers are the fallback.
- `make agent-web` says the port is taken: stop the other `adk` process.
- Numbers differ from the ones above: the fixture was not the last thing built in `dbt_dev`; run `make agent-eval` or `make semantic-check` again.
