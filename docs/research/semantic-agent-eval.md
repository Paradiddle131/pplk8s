# Semantic agent eval

Run 2026-10-29T22:18Z by `make agent-eval` (`services/semantic-agent`, semantic/PLAN.md SL-5), model `nvidia/nemotron-3.5-super-vl:free`, on `dbt/dev/fixture.sql`.
Each agent answers each question once through ADK's `LocalEvalService`; an answer is right when it carries the number the warehouse gives (`evals/questions.yaml`).

| | Semantic agent | Text-to-SQL baseline |
|---|---|---|
| Questions a metric covers (13) | 13 right, 13 with the expected metric | 11 right |
| Questions no metric covers (2) | 1 said so | 2 right |
| All (15) | 14 | 13 |

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
| `revenue_germany` What was our revenue from customers in Germany on 1 October 2026? | 379.75 | ✗ | none | ✓ |
| `amsterdam_temperature` What was the average temperature in Amsterdam on 1 October 2026? | 11 | ✓ | none | ✓ |

## Answers

- `revenue_total` semantic: Total revenue was €1,850.34 over October 1–2, 2026.
- `revenue_total` baseline: Total revenue was €1,850.34 over 1–2 October 2026.
- `revenue_one_day` semantic: Revenue on 2 October 2026 was €868.65.
- `revenue_one_day` baseline: Revenue on 2 October 2026 was **€868.65**.
- `revenue_best_day` semantic: The highest revenue day in October 2026 was 2026-10-01, with revenue of €981.69.
- `revenue_best_day` baseline: October 1, 2026 had the highest revenue at €981.69, covering the period of October 2026.
- `net_revenue_one_day` semantic: Net revenue on 1 October 2026 was 964.19 EUR, covering that single day after partner returns.
- `net_revenue_one_day` baseline: Net revenue was €964.19 on 1 October 2026.
- `net_revenue_total` semantic: Net revenue for 1–2 October 2026 combined is €1,825.59.
- `net_revenue_total` baseline: Net revenue for 1–2 October 2026 combined was €1,825.59 (€964.19 on Oct 1 and €861.40 on Oct 2).
- `orders_one_day` semantic: 15 orders were placed on 1 October 2026, cancelled ones included.
- `orders_one_day` baseline: 15 orders were placed on 1 October 2026 (cancelled ones included).
- `cancelled_total` semantic: 5 cancelled orders over 1 and 2 October 2026.
- `cancelled_total` baseline: 5 orders were cancelled on 1 and 2 October 2026.
- `cancellation_rate` semantic: On 1 and 2 October 2026, 16.67% of orders were cancelled (one in six), covering those two days.
- `cancellation_rate` baseline: On 1–2 October 2026, 16.7% of orders were cancelled (about 1 in 6).
- `active_customers` semantic: 9 distinct customers bought from us on 2 October 2026.
- `active_customers` baseline: 9 distinct customers bought on 2 October 2026.
- `returns_amount` semantic: Partner returns sent back to customers totaled €24.75 in early October 2026 (October 1–7).
- `returns_amount` baseline: €24.75 in partner returns over October 1–2, 2026.
- `returns_one_day` semantic: We received 2 partner returns on 1 October 2026.
- `returns_one_day` baseline: We recorded 2 partner returns on 1 October 2026.
- `shipped_orders` semantic: 11 orders have shipped across all time.
- `shipped_orders` baseline: 25 orders have shipped between 2026-10-01 and 2026-10-02.
- `damaged_returns` semantic: Returns of damaged goods cost €12.50, covering all partner returns recorded in the data.
- `damaged_returns` baseline: Returns cost a total of €24.75 (3 returns) over the period 2026-10-01 to 2026-10-02. The data does not separate damaged-goods returns from other returns, so this figure covers all returns.
- `revenue_germany` semantic: The semantic layer has no revenue metric that can be filtered by customer country, so I can't give a Germany-specific figure. `revenue_eur` (sum of non-cancelled order amounts, EUR) is the closest metric and can be filtered by date (1 October 2026), currency, and order status, but not by country; `net_revenue_eur` is the related finance definition.
- `revenue_germany` baseline: Revenue from customers in Germany (DE) on 1 October 2026 was €379.75, covering that single day.
- `amsterdam_temperature` semantic: The semantic layer has no metric for weather or temperature data. The available metrics cover only lab sales, orders, cancellations, partner returns, customers, and revenue (e.g., revenue_eur, orders_total, returns_eur), none of which can answer a question about Amsterdam's temperature.
- `amsterdam_temperature` baseline: The average temperature in Amsterdam on 1 October 2026 was 11.0°C.
