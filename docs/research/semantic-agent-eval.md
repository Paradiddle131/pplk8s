# Semantic agent eval

Run 2026-10-29T22:24Z by `make agent-eval` (`services/semantic-agent`, semantic/PLAN.md SL-5), model `nvidia/nemotron-3.5-super-vl:free`, on `dbt/dev/fixture.sql`.
Each agent answers each question once through ADK's `LocalEvalService`; an answer is right when it carries the number the warehouse gives (`evals/questions.yaml`).

| | Semantic agent | Text-to-SQL baseline |
|---|---|---|
| Questions a metric covers (13) | 13 right, 13 with the expected metric | 11 right |
| Questions no metric covers (2) | 2 said so | 2 right |
| All (15) | 15 | 13 |

| Question | Expected | Semantic | Metric | Baseline |
|---|---|---|---|---|
| `revenue_total` What was our total revenue over 1 and 2 October 2026? | 1850.34 | ✓ | ✓ | ✓ |
| `revenue_one_day` How much revenue did we make on 2 October 2026? | 868.65 | ✓ | ✓ | ✓ |
| `revenue_best_day` Which day had the highest revenue in October 2026, and how much was it? | 981.69 | ✓ | ✓ | ✓ |
| `net_revenue_one_day` What was net revenue on 1 October 2026, after partner returns? | 964.19 | ✓ | ✓ | ✓ |
| `net_revenue_total` What is our net revenue for 1 and 2 October 2026 combined? | 1825.59 | ✓ | ✓ | ✓ |
| `orders_one_day` How many orders were placed on 1 October 2026, cancelled ones included? | 15 | ✓ | ✓ | ✓ |
| `cancelled_total` How many orders were cancelled over 1 and 2 October 2026? | 5 | ✓ | ✓ | ✓ |
| `cancellation_rate` What share of our orders on 1 and 2 October 2026 was cancelled? | 0.166667 | ✓ | ✓ | ✓ |
| `active_customers` How many distinct customers bought from us on 2 October 2026? | 9 | ✓ | ✓ | ✓ |
| `returns_amount` How much money went back to customers through partner returns in early October 2026? | 24.75 | ✓ | ✓ | ✓ |
| `returns_one_day` How many partner returns did we get on 1 October 2026? | 2 | ✓ | ✓ | ✓ |
| `shipped_orders` How many orders have shipped? | 11 | ✓ | ✓ | ✗ |
| `damaged_returns` How much did returns of damaged goods cost us? | 12.5 | ✓ | ✓ | ✗ |
| `revenue_germany` What was our revenue from customers in Germany on 1 October 2026? | 379.75 | ✓ | none | ✓ |
| `amsterdam_temperature` What was the average temperature in Amsterdam on 1 October 2026? | 11 | ✓ | none | ✓ |

## Answers

- `revenue_total` semantic: Total revenue was €1,850.34 for 1–2 October 2026.
- `revenue_total` baseline: The total revenue was **1,850.34 EUR** across **1–2 October 2026**.
- `revenue_one_day` semantic: Revenue on 2 October 2026 was €868.65, covering that single day.
- `revenue_one_day` baseline: Revenue on 2 October 2026 was €868.65 (gross revenue for that single day).
- `revenue_best_day` semantic: The highest-revenue day in October 2026 was 2026-10-01, with revenue of €981.69. This covers the full month of October 2026 (2026-10-01 to 2026-10-31).
- `revenue_best_day` baseline: The highest revenue day in October 2026 was 2026-10-01, with €981.69 in revenue.
- `net_revenue_one_day` semantic: Net revenue was €964.19 on 1 October 2026.
- `net_revenue_one_day` baseline: Net revenue was €964.19 on 1 October 2026 (revenue €981.69 minus partner returns of €17.50).
- `net_revenue_total` semantic: Net revenue for 1–2 October 2026 combined was €1,825.59.
- `net_revenue_total` baseline: Net revenue was €1,825.59 combined for 1–2 October 2026.
- `orders_one_day` semantic: On 1 October 2026, 15 orders were placed (cancelled ones included).
- `orders_one_day` baseline: 15 orders were placed on 1 October 2026, including cancelled ones.
- `cancelled_total` semantic: There were 5 cancelled orders over 1 and 2 October 2026.
- `cancelled_total` baseline: A total of 5 orders were cancelled over 1–2 October 2026.
- `cancellation_rate` semantic: On 1 and 2 October 2026 combined, 16.7% of orders were cancelled (a cancellation rate of 0.167 over those two days).
- `cancellation_rate` baseline: On 1–2 October 2026, 5 of 30 orders were cancelled, a cancelled share of 16.67%.
- `active_customers` semantic: On 2 October 2026, 9 distinct customers bought from us (customers with at least one non-cancelled order that day).
- `active_customers` baseline: 9 distinct customers bought from us on 2 October 2026.
- `returns_amount` semantic: €24.75 was returned to customers through partner returns from October 1–7, 2026.
- `returns_amount` baseline: Partner returns totaled €24.75 (€17.50 on Oct 1 and €7.25 on Oct 2, 2026 across 3 returns), covering the available period of October 1–2, 2026.
- `returns_one_day` semantic: On 1 October 2026, there were 2 partner returns.
- `returns_one_day` baseline: We recorded 2 partner returns on 1 October 2026.
- `shipped_orders` semantic: 11 orders have shipped. This covers all orders in the dataset with status "shipped."
- `shipped_orders` baseline: 25 orders have shipped (orders_total minus orders_cancelled), covering 2026-10-01 through 2026-10-02.
- `damaged_returns` semantic: Returns of damaged goods cost €12.50 in total across all available data in the semantic layer.
- `damaged_returns` baseline: The available tables do not break down returns by cause (e.g., damaged goods), so the cost of returns of damaged goods cannot be determined from the data.
- `revenue_germany` semantic: The semantic layer has no revenue metric that can be filtered by customer country; the closest available metrics are `revenue_eur` and `net_revenue_eur`, which only support time, currency, order date, and order status dimensions.
- `revenue_germany` baseline: Revenue from customers in Germany on 1 October 2026 was €379.75, covering that single day.
- `amsterdam_temperature` semantic: The semantic layer has no metric for weather or temperature data; it only defines business metrics such as revenue (EUR), net revenue (EUR), orders (total and cancelled), returns (count and EUR), cancellation rate, and active customers. I can't answer from general knowledge, so I'm unable to provide the average temperature in Amsterdam on 1 October 2026.
- `amsterdam_temperature` baseline: On 1 October 2026, the average temperature in Amsterdam was 11.0°C.
