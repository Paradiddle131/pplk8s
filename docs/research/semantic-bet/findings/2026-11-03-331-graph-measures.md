# Which metrics compile to BigQuery graph measures (#331, part 1)

Question (Q6, offline part): which of the project's 57 metrics can become graph measures, and what is the property graph that holds them?
The live part (dry-running the statement, the graph beside the tables in a `bet-graph` data agent, and the agent's SQL per probe question) waits on the cost check ([#338](../../../../../issues/338)).

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

- A graph carries the definitions of the metrics that live on one table, about half of ours (30 to 35 of 57), the same half Lightdash keeps (36 of 56, [its finding](2026-11-03-334-lightdash.md)) and the OSI export keeps whole.
- What every native or open path drops is the same set: cumulative, conversion, offsets, cross-table ratios and derived metrics, percentiles, semi-additive and metric-filtered metrics; that set is where a gap-filling layer, or MetricFlow itself at query time, still earns its place.
- Whether a data agent aggregates through `AGG(measure)` when it also has the tables is the live question, and the docs only say agents "can take advantage of" measures.

## Still unknown

- Whether BigQuery accepts the statement as written (a dry run, live after #338), including the same table as a node and as an edge (`silver.orders` as `orders` and `orders_to_customers`).
- What a data agent does with the graph beside the tables, per probe question.
- Whether measures are GA by the time the report lands (#335 watches).

## Sources

- [Graph measures](https://docs.cloud.google.com/bigquery/docs/graph-measures), read 2026-11-03; the starting point's graph lines ([2026-11-02](2026-11-02-324-starting-point.md)).
