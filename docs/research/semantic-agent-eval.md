# Semantic agent eval

Run 2026-10-29T22:13Z by `make agent-eval` (`services/semantic-agent`, semantic/PLAN.md SL-5), model `nvidia/nemotron-3.5-super-vl:free`, on `dbt/dev/fixture.sql`.
Each agent answers each question once through ADK's `LocalEvalService`; an answer is right when it carries the number the warehouse gives (`evals/questions.yaml`).

| | Semantic agent | Text-to-SQL baseline |
|---|---|---|
| Questions a metric covers (13) | 11 right, 12 with the expected metric | 11 right |
| Questions no metric covers (2) | 2 said so | 2 right |
| All (15) | 13 | 13 |

| Question | Expected | Semantic | Metric | Baseline |
|---|---|---|---|---|
| `revenue_total` What was our total revenue over 1 and 2 October 2026? | 1850.34 | ✓ | ✓ | ✓ |
| `revenue_one_day` How much revenue did we make on 2 October 2026? | 868.65 | ✓ | ✓ | ✓ |
| `revenue_best_day` Which day had the highest revenue in October 2026, and how much was it? | 981.69 | ✓ | ✓ | ✓ |
| `net_revenue_one_day` What was net revenue on 1 October 2026, after partner returns? | 964.19 | ✓ | ✓ | ✓ |
| `net_revenue_total` What is our net revenue for 1 and 2 October 2026 combined? | 1825.59 | ✓ | ✓ | ✓ |
| `orders_one_day` How many orders were placed on 1 October 2026, cancelled ones included? | 15 | ✓ | ✓ | ✓ |
| `cancelled_total` How many orders were cancelled over 1 and 2 October 2026? | 5 | ✓ | ✓ | ✓ |
| `cancellation_rate` What share of our orders on 1 and 2 October 2026 was cancelled? | 0.166667 | ✗ | ✓ | ✓ |
| `active_customers` How many distinct customers bought from us on 2 October 2026? | 9 | ✓ | ✓ | ✓ |
| `returns_amount` How much money went back to customers through partner returns in early October 2026? | 24.75 | ✓ | ✓ | ✓ |
| `returns_one_day` How many partner returns did we get on 1 October 2026? | 2 | ✓ | ✓ | ✓ |
| `shipped_orders` How many orders have shipped? | 11 | ✗ | ✗ | ✗ |
| `damaged_returns` How much did returns of damaged goods cost us? | 12.5 | ✓ | ✓ | ✗ |
| `revenue_germany` What was our revenue from customers in Germany on 1 October 2026? | 379.75 | ✓ | none | ✓ |
| `amsterdam_temperature` What was the average temperature in Amsterdam on 1 October 2026? | 11 | ✓ | none | ✓ |

## Answers

- `revenue_total` semantic: Total revenue was €1,850.34, covering 1–2 October 2026 inclusive.
- `revenue_total` baseline: Total revenue was €1,850.34 over 1–2 October 2026.
- `revenue_one_day` semantic: On 2 October 2026, revenue was €868.65.
- `revenue_one_day` baseline: On 2 October 2026, revenue was €868.65 EUR.
- `revenue_best_day` semantic: The highest-revenue day in October 2026 was October 1, 2026, with revenue of 981.69 EUR.
- `revenue_best_day` baseline: The highest revenue day in October 2026 was October 1, 2026, with €981.69.
- `net_revenue_one_day` semantic: Net revenue on 1 October 2026 was €964.19, covering that single day.
- `net_revenue_one_day` baseline: Net revenue after partner returns was €964.19 on 1 October 2026.
- `net_revenue_total` semantic: Net revenue for 1 and 2 October 2026 combined was 1,825.59 EUR.
- `net_revenue_total` baseline: Net revenue for 1 and 2 October 2026 combined is €1,825.59.
- `orders_one_day` semantic: On 1 October 2026, 15 orders were placed (cancelled ones included).
- `orders_one_day` baseline: On 1 October 2026, 15 orders were placed (including 2 cancelled).
- `cancelled_total` semantic: 5 cancelled orders over 1–2 October 2026.
- `cancelled_total` baseline: 5 cancelled orders, covering 1 and 2 October 2026.
- `cancellation_rate` semantic: 16.7% of orders were cancelled, covering 1–2 October 2026.
- `cancellation_rate` baseline: On 1 and 2 October 2026, 16.67% of orders were cancelled (5 out of 30 orders).
- `active_customers` semantic: On 2 October 2026, 9 distinct customers made a purchase (defined as having at least one non-cancelled order).
- `active_customers` baseline: On 2 October 2026, 9 distinct customers bought from us.
- `returns_amount` semantic: €24.75 went back to customers through partner returns, covering October 1–7, 2026.
- `returns_amount` baseline: €24.75 was returned to customers across October 1–2, 2026 (the only early-October dates in the net_sales_daily table): €17.50 on Oct 1 (2 returns) and €7.25 on Oct 2 (1 return).
- `returns_one_day` semantic: On 1 October 2026, there were 2 partner returns.
- `returns_one_day` baseline: We received 2 partner returns on 1 October 2026.
- `shipped_orders` semantic: The semantic layer has no metric for shipped orders. The closest available metrics are **orders_total** (all orders placed, cancelled included) and **orders_cancelled** (orders with status cancelled).
- `shipped_orders` baseline: 25 orders have shipped, covering the period from 2026‑10‑01 to 2026‑10‑02.
- `damaged_returns` semantic: Returns of damaged goods cost **€12.50 EUR** (across all time periods in the data).
- `damaged_returns` baseline: Returns of goods cost €24.75 over the period from 2026-10-01 to 2026-10-02.
- `revenue_germany` semantic: The semantic layer has no metric that breaks revenue down by customer country, so I cannot report revenue specifically for customers in Germany. The closest available metrics are `revenue_eur` (Revenue (EUR), sum of amount for non-cancelled orders) and `net_revenue_eur` (Net revenue (EUR), revenue minus partner returns), neither of which has a customer country dimension.
- `revenue_germany` baseline: Revenue from customers in Germany on 1 October 2026 was €379.75.
- `amsterdam_temperature` semantic: The semantic layer has no temperature metric; it only defines sales and finance metrics such as revenue_eur, orders_total, cancellation_rate, net_revenue_eur, returns_eur, returns_count, orders_cancelled, and customers_distinct. I cannot answer the weather question from this data.
- `amsterdam_temperature` baseline: The average temperature in Amsterdam on 1 October 2026 was 11.0°C.
