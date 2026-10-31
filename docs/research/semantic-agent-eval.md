# Semantic agent eval

Run 2026-10-31T13:15Z by `make agent-eval` (`services/semantic-agent`, semantic/PLAN.md SL-5), model `nvidia/nemotron-3.5-super-vl:free`, on `dbt/dev/fixture.sql`.
Each agent answers each question once through ADK's `LocalEvalService`; an answer is right when it carries the number the warehouse gives (`evals/questions.yaml`).

| | Semantic agent | Text-to-SQL baseline |
|---|---|---|
| Questions a metric covers (17) | 17 right, 17 with the expected metric, 17 quoting their freshness | 15 right |
| Questions no metric covers (1) | 1 said so | 1 right |
| All (18) | 18 | 16 |

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
| `returns_one_day` How many partner returns did we get on 1 October 2026? | 2 | ✓ | ✓ | ✓ | ✓ |
| `shipped_orders` How many orders have shipped? | 11 | ✓ | ✓ | ✓ | ✗ |
| `damaged_returns` How much did returns of damaged goods cost us? | 12.5 | ✓ | ✓ | ✓ | ✗ |
| `revenue_germany` What was our revenue from customers in Germany on 1 October 2026? | 379.75 | ✓ | ✓ | ✓ | ✓ |
| `amsterdam_temperature` What was the average temperature in Amsterdam on 1 October 2026? | 11 | ✓ | none | none | ✓ |
| `cost_per_booking_total` What was our cost per booking over 1 and 2 October 2026? | 130 | ✓ | ✓ | ✓ | ✓ |
| `cost_per_lead_search` How much did a lead from search campaigns cost us in early October 2026? | 46 | ✓ | ✓ | ✓ | ✓ |
| `lead_to_booking_rate` What share of our leads from 1 and 2 October 2026 went on to book? | 0.3 | ✓ | ✓ | ✓ | ✓ |

## Answers

- `revenue_total` semantic: Total revenue was EUR 1,850.34 over 1–2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_total` baseline: Total revenue was €1,850.34 across 1 and 2 October 2026.
- `revenue_one_day` semantic: Revenue on 2 October 2026 was €868.65, covering that single day. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_one_day` baseline: Revenue on 2 October 2026 was €868.65.
- `revenue_best_day` semantic: The highest-revenue day in October 2026 was 2026-10-01, with revenue of €981.69. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_best_day` baseline: The highest-revenue day in October 2026 was 2026-10-01, with €981.69 in revenue.
- `net_revenue_one_day` semantic: Net revenue on 1 October 2026 was €964.19, covering revenue minus partner returns for that single day. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `net_revenue_one_day` baseline: Net revenue was €964.19 on 1 October 2026 (gross revenue €981.69 minus partner returns of €17.50).
- `net_revenue_total` semantic: Net revenue was 1,825.59 EUR for 1 and 2 October 2026 combined. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `net_revenue_total` baseline: Combined net revenue for 1–2 October 2026 is €1,825.59 (€964.19 on 1 October plus €861.40 on 2 October).
- `orders_one_day` semantic: On 1 October 2026, 15 orders were placed, cancelled ones included. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `orders_one_day` baseline: 15 orders were placed on 1 October 2026, including cancelled ones.
- `cancelled_total` semantic: 5 cancelled orders were placed over 1 and 2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cancelled_total` baseline: 5 orders were cancelled on 1 and 2 October 2026.
- `cancellation_rate` semantic: On 1 and 2 October 2026, the share of orders cancelled was 16.7%. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cancellation_rate` baseline: On 1 and 2 October 2026, 16.67% of the 30 orders were cancelled.
- `active_customers` semantic: 9 distinct customers bought from us on 2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `active_customers` baseline: 9 distinct customers bought on 2 October 2026.
- `returns_amount` semantic: Partner returns returned €24.75 to customers between 2026-10-01 and 2026-10-07. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `returns_amount` baseline: €24.75 was returned to customers through partner returns between October 1 and October 2, 2026.
- `returns_one_day` semantic: There were 2 partner returns on 1 October 2026. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `returns_one_day` baseline: On 1 October 2026 there were 2 returns (€17.50 in returned value).
- `shipped_orders` semantic: There are 11 shipped orders (all time). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `shipped_orders` baseline: 25 orders have shipped, covering the period from 2026-10-01 to 2026-10-02.
- `damaged_returns` semantic: Returns of damaged goods cost €12.50 across all available return data. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `damaged_returns` baseline: The tables do not separate returns of damaged goods from other returns; total returns cost €24.75 (3 returns) across 2026-10-01 to 2026-10-02.
- `revenue_germany` semantic: Revenue from customers in Germany on 1 October 2026 was €379.75, covering that single day. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_germany` baseline: Revenue from customers in Germany on 1 October 2026 was €379.75 (3 orders).
- `amsterdam_temperature` semantic: The semantic layer has no metric for temperature or weather; it only tracks business measures such as revenue, orders, bookings, ad spend, leads, and returns. There is no metric that can answer the average temperature in Amsterdam on 1 October 2026.
- `amsterdam_temperature` baseline: The average temperature in Amsterdam on 1 October 2026 was 11°C, covering that single day.
- `cost_per_booking_total` semantic: Cost per booking was EUR 130.0 over 1 and 2 October 2026. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cost_per_booking_total` baseline: The combined cost per booking on 1–2 October 2026 was €130.00 per booking (€220 on 1 Oct for 1 booking; €85 on 2 Oct for 2 bookings).
- `cost_per_lead_search` semantic: A lead from search campaigns cost €46.00 per lead over October 1–7, 2026 (early October). Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cost_per_lead_search` baseline: A search-campaign lead cost €46 on average across early October 2026 (Oct 1–2): €230 total ad spend divided by 5 leads (€43.33/lead on Oct 1, €50/lead on Oct 2).
- `lead_to_booking_rate` semantic: 30% of the leads created on 1 and 2 October 2026 booked within 30 days of creation. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `lead_to_booking_rate` baseline: 30% of leads booked — 3 bookings from 10 leads across 1–2 October 2026.
