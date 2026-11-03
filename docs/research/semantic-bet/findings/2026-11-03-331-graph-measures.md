# Which metrics compile to BigQuery graph measures, and whether a data agent uses them (#331)

Question (Q6): which of the project's 57 metrics can become graph measures, and what is the property graph that holds them (part 1, offline)?
Does BigQuery take that graph, and does a data agent with the graph beside the tables aggregate through its measures (part 2, live, [below](#part-2-live-on-the-lab-project-2026-11-03))?

## What was run

- 2026-11-03T02:02Z, offline: [`probes/331_graph_measures.py`](../probes/331_graph_measures.py) on the manifest of `dbt/` parsed on the compile-only `bigquery` target (dbt 1.12.6; all 57 metrics, the approximate median included).
  It classifies every metric under the documented rules and writes [`probes/331_bet_graph.sql`](../probes/331_bet_graph.sql), the `CREATE PROPERTY GRAPH bet_graph.metrics` statement (12 node tables, 11 edge tables); two runs wrote the same file.
- The translation is the probe's, not MetricFlow's: a simple metric's `Dimension()` filters on its own model become a `CASE` inside its aggregate; ratios become `SAFE_DIVIDE(AGG(numerator), NULLIF(AGG(denominator), 0))`; nothing was run on BigQuery.

## The rules (`stated`, [graph measures](https://docs.cloud.google.com/bigquery/docs/graph-measures), read 2026-11-03)

- Measures are declared in a node or edge table's `PROPERTIES` as `MEASURE(<expr>) AS <name>`; aggregates `SUM`, `AVG`, `COUNT`, `MIN`, `MAX` (each with `DISTINCT`) and `AGG()` for derived measures; scalar arithmetic over aggregates and `CASE` inside an aggregate are allowed.
- Derived measures reference measures "defined on the same element table" and "retain the grain-locking property of the underlying element table key".
- GQL can't reference a measure; SQL reads it through `GRAPH_EXPAND` with `AGG()`, on demand; GQL needs an Enterprise reservation; the page states no launch stage (the starting point recorded Preview since 2026-04-22).

## What was observed (`measured`, the run above)

- 30 of 57 compile: simple 26 of 33, ratio 4 of 10, derived 0 of 4, cumulative 0 of 6, conversion 0 of 4.
- The 27 that don't, by reason:
  - 10 have no form at all: 6 cumulative, 4 conversion (a window or a funnel).
  - 3 derived are offsets in time (`*_wow_growth`).
  - 4 combine tables: `net_revenue_eur` and `return_rate` (orders and returns), `cost_per_lead_eur` and `cost_per_booking_eur` (ad spend with leads or bookings).
  - 1 percentile (`median_order_value_eur`), 1 semi-additive (`remaining_budget_eur`, the last snapshot per campaign).
  - 2 filter through another metric (`repeat_customers`, `revenue_repeat_customers_eur`: `Metric('orders_total', group_by=['customer']) >= 2`), and `repeat_revenue_share` with them.
  - 3 sit on models without a primary entity (`ad_clicks`, `ad_spend_eur`, `candidates_in_stage`), and 2 ratios have a filtered input (`average_order_value_eur`, `damaged_return_share`): these 5 are the probe's limits, not the graph's; a declared composite key and a filtered helper measure would make them compile, so 35 is the ceiling on this project.
- The graph keeps what makes measures worth having: `revenue_eur` is `MEASURE(SUM(CASE WHEN (status <> 'cancelled') THEN amount END))` on `orders`, grain-locked to `order_id`, so slicing it by a customer's country through the `orders_to_customers` edge cannot double-count.

## What it means for the verdict

- A graph carries the definitions of the metrics that live on one table, about half of ours (30 to 35 of 57), close to the set Lightdash keeps (36 of 56, [its finding](2026-11-03-334-lightdash.md)).
- What every native or open path drops is the same set: cumulative, conversion, offsets, cross-table ratios and derived metrics, percentiles, semi-additive and metric-filtered metrics; that set is where a gap-filling layer, or MetricFlow itself at query time, still earns its place.
- Whether a data agent aggregates through `AGG(measure)` when it also has the tables is the live question, and the docs only say agents "can take advantage of" measures.

## Part 2, live on the lab project (2026-11-03)

### What was run

- 06:52Z: `make gcp-cost-check` and `make gcp-usage-check` ok ($0.000010 this month, under the accepted $1.00); dataset `bet_graph` in `US`.
- `bq query --dry_run` of part 1's statement: "Query successfully validated", 0 bytes; then the statement, three times, each refusal fixed in [`probes/331_graph_measures.py`](../probes/331_graph_measures.py) and the file regenerated from the `gcp` target's manifest ([`probes/326_dbt_artifacts.sh`](../probes/326_dbt_artifacts.sh), dbt 1.12.6; before the fixes it reproduced part 1's file byte for byte).
- 06:53Z: `bet_graph.metrics` (12 node, 11 edge tables) created; a `GRAPH_EXPAND` query on it refused.
- 06:54Z: `--only orders,customers,returns --graph sales` wrote [`probes/331_bet_graph_sales.sql`](../probes/331_bet_graph_sales.sql), `bet_graph.sales` (3 node, 3 edge tables), created; its measures queried with `GRAPH_EXPAND` and `AGG()`.
- 06:55Z to 06:58Z: [`probes/331_graph_agent.py`](../probes/331_graph_agent.py) created the data agent `projects/pplk8s-lab-001/locations/us/dataAgents/bet-graph` (the three silver tables, `propertyGraphReferences` to `bet_graph.sales`, one sentence naming the graph as the metric definitions, the lab's byte cap) through `publish.py`'s publisher, and asked four questions, twice; rows in [`2026-11-03-331-graph-measures.jsonl`](2026-11-03-331-graph-measures.jsonl).
- 06:59Z: the cost and usage checks again (ok, unchanged); `JOBS_BY_USER` since 06:52Z: 39 query jobs, 280 MiB billed, the agent's 8 of them 120 MiB.

### What was observed (`measured`, the runs above)

- The dry run validates nothing in a graph statement: it passed a statement BigQuery then refused twice.
  - "Columns are not supported in graph measure property expressions": a measure may read only declared properties, and `time_to_hire_days` read `days_to_hire`, which wasn't one; the generator now declares every column a measure reads (8 columns on 7 node tables: `days_to_hire`, `amount` twice, `customer_id` twice, `session_id`, `first_replied_ts`, `partner_id`).
  - "A measure expression must contain at least one aggregate function referencing a graph property": `MEASURE(COUNT(1))` is refused; the generator counts the node's key instead (`bookings` and `leads` now `COUNT(booking_id)`, `COUNT(lead_id)`).
- "Property graph has 12 node tables, which exceeds the maximum of 10": `GRAPH_EXPAND` refuses a graph of more than ten node tables; the graph is created, then unusable for measures; the docs page doesn't state the limit (read 2026-11-03). One graph per domain is the shape that works; the project's 16 semantic models need at least two.
- `SELECT *` from `GRAPH_EXPAND` is refused ("Returning expressions of type MEASURE is not allowed"); the expanded columns are named `<node>_<property>`.
- The measures give the semantic layer's numbers: September 2026 revenue by customer country through `AGG(orders_revenue_eur)` is DE 2,665.50, FR 1,241, GB 2,634, NL 2,408, TR 2,412, US 1,222.25, exactly `bet_shaped.sales_by_country_daily`'s (#329), with no cancelled orders and no fan-out through the `orders_to_customers` edge.
- From `start_node => 'returns'` the expansion carries returns' own properties but not `customers_country` ("Unrecognized name"), though the graph has `returns_to_customers`; returns reach customers by two paths (directly and through orders), and the docs say ambiguous edges are ignored: likely the cause, not confirmed.
- The data agent saw the graph and never used it: each of the 8 chats began "Retrieving context for 3 tables and 1 graph", and none of the 8 generated queries named `GRAPH_EXPAND`, `GRAPH_TABLE` or a measure; all 8 were plain SQL over silver.
- Its answers, against the measures' definitions: cancellation rate right in both runs (8.33 %, 10 of 120), returns by country right in both (DE 39.75, NL 30, TR 15, FR 5); revenue by country wrong in run 1 (DE 2,857.00: `SUM(amount)` with cancelled orders, the definition the `revenue_eur` measure carries in its `CASE`) and right in run 2; average order value wrong in both (113.86, `AVG(amount)` over all 120 orders, against the defined 114.39 over non-cancelled ones; not a measure in the graph, its denominator filtered).
- So 5 of 8 right, all through the agent's own SQL; the measures that would have fixed run 1's revenue sat in the context unused.

### What it means for the verdict

- A graph is a valid, exact carrier for single-table metric definitions on BigQuery (the numbers match MetricFlow's), queryable on demand pricing through `GRAPH_EXPAND`, but at ten node tables per graph and with path ambiguity that silently drops a join.
- As grounding for Google's data agent it did nothing measurable here: the agent knew the graph was there and wrote SQL against the tables. The docs' "data agents can take advantage of measures" did not hold for these questions in these runs.
- The wrong answers are the usual ones (cancelled orders counted), which is exactly what the measures encode: the gap is not the definition's absence but the agent's not reading through it.

### Still unknown (part 2)

- Whether a graph-only context (no tables) or an instruction to use `GRAPH_EXPAND` changes the agent's behaviour: not tried (the table-function arm, #329, shows an instruction does move this agent).
- Rates: two runs of four questions; #333 scores the arm with k runs.
- Whether the ten-node limit and the ambiguous-path behaviour are documented elsewhere, or change by GA (#335 watches).

## Still unknown (part 1)

- ~~Whether BigQuery accepts the statement as written, including the same table as a node and as an edge~~: after two fixes, yes, the same table as node and edge included (part 2).
- ~~What a data agent does with the graph beside the tables~~: part 2.
- Whether measures are GA by the time the report lands (#335 watches).

## Sources

- [Graph measures](https://docs.cloud.google.com/bigquery/docs/graph-measures), read 2026-11-03; the starting point's graph lines ([2026-11-02](2026-11-02-324-starting-point.md)).
