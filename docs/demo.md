# Demo: an agent-ready warehouse on BigQuery, end to end

A screen-share script for a team whose data lands in BigQuery, whose agents guess which table to trust, and who will not run dbt Cloud ([`semantic/PLAN.md`](../semantic/PLAN.md) § 1).
It walks the whole use case (U1-U6): the layers and one calculated field, the documentation standard, an agent answering with its freshness, a freshness and a discrepancy alert, the audit trail, and the migration report.
The warehouse is the BigQuery emulator (`goccy/bigquery-emulator`, Compose profile `bigquery`), built by the same dbt project, unchanged; the agent, the freshness exporter and the audit trail run on the Compose Postgres, where the lab's agent and alerting live.
Everything runs on the dev fixture (`dbt/dev/fixture.sql`), so every number below is fixed and the script can be rehearsed in one sitting.

Every step is one command, `make demo STEP=<step>`, which prints what to show and fails when the output differs from this script.
`make demo-check` rehearses the whole script, every step asserted and timed, and spends no model quota.

## Before the call (about 17 minutes, once)

```bash
make services-up
make demo STEP=setup
```

- `setup` runs `make bigquery-emulator-check`: each domain on a fresh emulator of its own (one emulator holding every domain overflows its engine), the fixture copied in, `dbt build` of every layer with its tests, the metrics checked against the hand-written tables; the platform's models and the migration report go last, so that is what the emulator holds for the demo.
  It ends `PASS: BigQuery run check on the emulator`.
- It then builds the same fixture in the Compose warehouse's `dbt_dev` for the agent: the models, the catalog, the agents' read-only roles and the fixture's days in `ops.readiness`.
  It ends `ok: fixture built in dbt_dev, catalog written, agent roles granted, readiness recorded`.
- For the live agent (step 3), check the model key with `make agent-key-check`; for the score (step 7), `make agent-eval` refreshes it (about 90 free-tier model requests).

The emulator keeps its data in memory: after it restarts, run `setup` again.

## The script

**1. Layers, and one calculated field defined once (2 min, U1, U6).**

```bash
make demo STEP=layers
```

Expect one line per BigQuery dataset: `bronze` (the landing tables, cast), `silver` (one row per key, latest load wins), `gold` and `exposed` (what people and agents read), `semantic` (`metrics`, `glossary`), then `legacy`, `migration` and `ops`.
Then cost per lead and per booking, queried through MetricFlow on BigQuery:

| campaign__channel | cost_per_lead_eur | cost_per_booking_eur |
|---|---|---|
| email | 10.0 | |
| search | 46.0 | 115.0 |
| social | 46.67 | 140.0 |

and over the whole period 39.0 and 130.0.
Open `dbt/models/semantic/semantic.yml` at `cost_per_booking_eur`: a ratio of two measures, total spend over total bookings, never an average of daily ratios.
Say: every dashboard, export and agent gets this number from this one definition; email has no booking, so no cost per booking, rather than a division by zero.

**2. The documentation standard (2 min, U2).**

```bash
make demo STEP=standard
```

Expect `check_standard: 67 models named by layer; 17 public models, 15 semantic models, 39 metrics and 7 saved queries described`, then `gold.daily_sales` as BigQuery holds it: the table's description and one per column (`revenue_eur  NUMERIC  Sum of amount for non-cancelled orders.`), written by dbt's `persist_docs`.
Say: the rules are in [`agent-ready-warehouse.md`](agent-ready-warehouse.md); the check fails a build that strays from them, and the descriptions an agent reads in BigQuery are the ones in the YAML.
Then open `dbt/target/catalog/data_agent/system_instruction.yaml`: the BigQuery data agent's authored context (tables, aggregations, relationships, glossary), generated from the same YAML ([mapping](semantic-layer-on-bigquery.md)).

**3. Ask the agent (3 min, U4).**

```bash
make agent-web AGENT_DBNAME=dbt_dev
```

Open `http://localhost:8000`, pick `semantic_agent`, and ask:
- "What was net revenue on 1 October 2026, after partner returns?"
  The answer is €964.19, then its freshness: "Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline."
  The events panel shows the tool calls: `query_metrics`, after `list_metrics` or `describe_metric` when the model looks the metric up first.
- "How many orders have shipped?"
  The answer is 11: `orders_total` filtered on `order__status = shipped`.
  Switch to `sql_baseline` and ask again: it has said 25 (orders minus cancellations), a confident wrong number from a table without the breakdown.
- "What was our revenue from customers in Germany on 1 October 2026?"
  The answer is €379.75: `revenue_eur` filtered on `customer__country = DE`, the customer's dimension joined through the order; `exposed.sales_by_country_daily` says the same.
- "What was the average temperature in Amsterdam on 1 October 2026?"
  The semantic agent says the semantic layer has no metric for it, rather than guessing; `sql_baseline` reads `gold.daily_weather` and says 11.0 °C.
  Say: the semantic agent answers only what the layer defines; a number it should answer becomes a metric first ([where each calculated field lives](agent-ready-warehouse.md#where-each-calculated-field-lives)).

The model is a free OpenRouter model; an answer takes 5 to 30 seconds, and a spent quota answers "No answer: the model's daily request quota is spent." instead of failing.
`make demo STEP=agent` asks the first question with a scripted model and the real tools, and prints the same figure and freshness: the fallback when the model is unavailable.

**4. Two alerts (3 min, U3).**

```bash
make demo STEP=alerts
```

First, a source that stops flowing: `dbt source freshness` passes on fresh data, then fails on a table whose loads stopped (`ok: a stopped source fails it (exit 1) and records error, …`); the warehouse's `sql_exporter` exports each verdict, and `SourceStale` fires on it (its promtool tests).
Then a discrepancy: the script adds €10 to one day's search spend in `gold.marketing_daily` on BigQuery, as a hand edit or a broken job would, and runs the layer hops:

```text
1 of 3 PASS hop_gold_to_exposed_channel_performance_daily
2 of 3 FAIL 1 hop_metric_ad_spend_eur_to_gld_marketing_daily
3 of 3 FAIL 1 hop_silver_to_gold_marketing_daily
```

and prints the mismatching key: `silver -> gold marketing_daily  2026-10-01`, spend 220 upstream against 230 in gold.
Say: these tests run in every `dbt build`, so the build that would publish the wrong number fails, with the hand-off and the day in its output; in Airflow that failed task is the alert (`AirflowTaskFailures`).
The script then rebuilds gold from silver and the hops pass again.

**5. The audit trail (1 min, U4).**

```bash
make demo STEP=audit
```

Expect the agent's calls, newest first: when, which agent, which tool, which metrics, how many rows, and the freshness it quoted.
Say: every `query_metrics` call writes one row through its own role, which can insert and nothing else; the same table builds on BigQuery from the same dbt macro, and the per-agent access proposal is [Agent access and audit](semantic-layer-on-bigquery.md#agent-access-and-audit).

**6. The migration report (2 min, U5).**

```bash
make demo STEP=migration
```

Expect `migration.parity` on BigQuery, one row per consumer and field: the finance dashboard matches on every field and has switched; the sales agent's `revenue` differs on 4 of 12 country-days, the ones with a cancelled order, so it waits on its old table until its owner accepts the difference; the marketing automation matches but waits for the agent.
Say: the old tables keep running while consumers move one at a time, dashboards first, and the build refuses a switch the report does not support ([`migration-rehearsal.md`](migration-rehearsal.md)).

**7. The score (1 min).**
Open [`docs/research/semantic-agent-eval.md`](research/semantic-agent-eval.md): fifteen questions, the same model, both agents.
As of the last run, the semantic agent was right on all 15 and quoted its freshness in all 13 metric answers; the text-to-SQL baseline was right on 12.

## The rehearsal

`make demo-check` runs `setup` and steps 1 to 6 in order, asks the agent again (the live agent reads the same `dbt/target` after every step), and ends with each step's time and `PASS: demo check`.
One run with every domain, Compose services already up and uv's cache warm (cloud sandbox, 2026-11-01): 1233 s.

| Step | Time | Mostly |
|---|---|---|
| setup | 998 s | `make bigquery-emulator-check`: six parts, each on a fresh emulator, one thread; the platform's alone is 160 nodes |
| layers | 22 s | two MetricFlow queries |
| standard | 2 s | |
| agent | 9 s | |
| alerts | 188 s | `make source-freshness-check` and `make rules-test` |
| audit | 1 s | |
| migration | 4 s | |
| agent again | 9 s | |

The steps shown live (1 to 6) take about 4 minutes of commands; the rest is talk.

## If something goes wrong

- A model answer that is slow or rate-limited: wait a minute and ask again, or show `make demo STEP=agent` and the eval's numbers.
- `make agent-web` says the port is taken: stop the other `adk` process.
- `no emulator build`, or an emulator query fails after a restart: run `make demo STEP=setup` again.
- `alerts` failed halfway and left the changed number in gold: `make demo STEP=setup` rebuilds everything.
- Agent numbers differ from the ones above: the fixture was not the last thing built in `dbt_dev`; run `make demo STEP=setup` again.

## Not on the emulator, and why

- The agent reads the Compose Postgres: its `query_metrics` runs MetricFlow through dbt-postgres, and its freshness reads `ops.readiness`, which the DAGs write there.
  The metric SQL it would send to BigQuery is what step 1 runs on the emulator.
- The freshness alert's exporter and Prometheus read the Compose Postgres; `dbt source freshness` itself is the same command on BigQuery.
- On real BigQuery: [`semantic-layer-on-bigquery.md`](semantic-layer-on-bigquery.md) says what is measured, stated and unverified.
