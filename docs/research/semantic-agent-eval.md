# Semantic agent eval

Run 2026-10-29T23:07Z by `make agent-eval` (`services/semantic-agent`, semantic/PLAN.md SL-5), model `nvidia/nemotron-3.5-super-vl:free`, on `dbt/dev/fixture.sql`.
Each agent answers each question once through ADK's `LocalEvalService`; an answer is right when it carries the number the warehouse gives (`evals/questions.yaml`).

| | Semantic agent | Text-to-SQL baseline |
|---|---|---|
| Questions a metric covers (13) | 13 right, 13 with the expected metric, 13 quoting their freshness | 10 right |
| Questions no metric covers (2) | 2 said so | 2 right |
| All (15) | 15 | 12 |

| Question | Expected | Semantic | Metric | Freshness | Baseline |
|---|---|---|---|---|---|
| `revenue_total` What was our total revenue over 1 and 2 October 2026? | 1850.34 | ✓ | ✓ | ✓ | ✓ |
| `revenue_one_day` How much revenue did we make on 2 October 2026? | 868.65 | ✓ | ✓ | ✓ | ✓ |
| `revenue_best_day` Which day had the highest revenue in October 2026, and how much was it? | 981.69 | ✓ | ✓ | ✓ | ✓ |
| `net_revenue_one_day` What was net revenue on 1 October 2026, after partner returns? | 964.19 | ✓ | ✓ | ✓ | ✓ |
| `net_revenue_total` What is our net revenue for 1 and 2 October 2026 combined? | 1825.59 | ✓ | ✓ | ✓ | ✓ |
| `orders_one_day` How many orders were placed on 1 October 2026, cancelled ones included? | 15 | ✓ | ✓ | ✓ | ✓ |
| `cancelled_total` How many orders were cancelled over 1 and 2 October 2026? | 5 | ✓ | ✓ | ✓ | ✓ |
| `cancellation_rate` What share of our orders on 1 and 2 October 2026 was cancelled? | 0.166667 | ✓ | ✓ | ✓ | ✓ |
| `active_customers` How many distinct customers bought from us on 2 October 2026? | 9 | ✓ | ✓ | ✓ | ✓ |
| `returns_amount` How much money went back to customers through partner returns in early October 2026? | 24.75 | ✓ | ✓ | ✓ | ✓ |
| `returns_one_day` How many partner returns did we get on 1 October 2026? | 2 | ✓ | ✓ | ✓ | ✗ |
| `shipped_orders` How many orders have shipped? | 11 | ✓ | ✓ | ✓ | ✗ |
| `damaged_returns` How much did returns of damaged goods cost us? | 12.5 | ✓ | ✓ | ✓ | ✗ |
| `revenue_germany` What was our revenue from customers in Germany on 1 October 2026? | 379.75 | ✓ | none | none | ✓ |
| `amsterdam_temperature` What was the average temperature in Amsterdam on 1 October 2026? | 11 | ✓ | none | none | ✓ |

## Answers

- `revenue_total` semantic: Total revenue was €1,850.34 over 1–2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_total` baseline: Total revenue was €1,850.34 over 1–2 October 2026.
- `revenue_one_day` semantic: Revenue on 2 October 2026 was €868.65, covering orders placed on that day. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_one_day` baseline: €868.65 in revenue on 2 October 2026.
- `revenue_best_day` semantic: The highest revenue day in October 2026 was 2026‑10‑01, with EUR 981.69 in revenue for that month. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_best_day` baseline: The highest revenue day in October 2026 was 2026-10-01, with revenue of €981.69.
- `net_revenue_one_day` semantic: Net revenue was €964.19 on 1 October 2026 (one day), covering revenue minus partner returns. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `net_revenue_one_day` baseline: Net revenue on 1 October 2026 was €964.19, covering that single day.
- `net_revenue_total` semantic: Net revenue for 1 and 2 October 2026 combined is €1,825.59. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `net_revenue_total` baseline: Combined net revenue for 1–2 October 2026 is €1,825.59.
- `orders_one_day` semantic: 15 orders were placed on 1 October 2026, cancelled ones included. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `orders_one_day` baseline: 15 orders were placed on 1 October 2026 (including the 2 cancelled ones).
- `cancelled_total` semantic: 5 cancelled orders were recorded over 1–2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cancelled_total` baseline: A total of 5 orders were cancelled across 1 and 2 October 2026.
- `cancellation_rate` semantic: 16.7% of the orders placed on 1 and 2 October 2026 were cancelled (covering both days combined). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cancellation_rate` baseline: 16.7% of orders were cancelled on 1–2 October 2026 (5 cancelled out of 30 total orders).
- `active_customers` semantic: 9 distinct customers bought from us on 2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `active_customers` baseline: On 2 October 2026, 9 distinct customers bought from us.
- `returns_amount` semantic: Partner returns totaled €24.75 for early October 2026 (October 1–7). Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `returns_amount` baseline: The available tables have no partner dimension, so I can only report total returns (returns_eur) in exposed.net_sales_daily, which covers just 2026-10-01 to 2026-10-02: €24.75 (€17.50 on Oct 1 + €7.25 on Oct 2).
- `returns_one_day` semantic: On 1 October 2026, there were 2 partner returns, covering that single day. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `returns_one_day` baseline: The available tables do not include a partner‑returns metric; only total returns are recorded (in `exposed.net_sales_daily.returns_count`), so partner returns for 1 October 2026 cannot be determined from the data.
- `shipped_orders` semantic: 11 orders have shipped, covering all available order data. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `shipped_orders` baseline: 25 orders have shipped, covering 2026-10-01 to 2026-10-02.
- `damaged_returns` semantic: Returns for damaged goods (reason: “damaged”) totaled **12.5 EUR** across the full period covered by the data. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `damaged_returns` baseline: Returns totaled €24.75 across 3 returns from 2026-10-01 to 2026-10-02. The data does not separate damaged-goods returns from other returns, so this is the total returns cost available.
- `revenue_germany` semantic: The semantic layer has no revenue metric broken down by customer country, so I can’t provide Germany‑specific revenue for 1 October 2026. The closest available metrics are `revenue_eur` and `net_revenue_eur`.
- `revenue_germany` baseline: Revenue from customers in Germany (DE) on 1 October 2026 was €379.75, across 3 orders.
- `amsterdam_temperature` semantic: The semantic layer has no metric for weather or temperature; its metrics cover lab sales, orders, cancellations, returns, and revenue (e.g., revenue_eur, orders_total, returns_eur). I can't answer from general knowledge.
- `amsterdam_temperature` baseline: The average temperature in Amsterdam on 1 October 2026 was 11.0 °C for that single day.
