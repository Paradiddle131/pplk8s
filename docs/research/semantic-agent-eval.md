# Semantic agent eval

Run 2026-10-30T23:48Z by `make agent-eval` (`services/semantic-agent`, semantic/PLAN.md SL-5), model `nvidia/nemotron-3.5-super-vl:free`, on `dbt/dev/fixture.sql`.
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

- `revenue_total` semantic: Total revenue for 1–2 October 2026 was EUR 1,850.34. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_total` baseline: Total revenue was €1,850.34 over 1–2 October 2026 (€981.69 on 1 October and €868.65 on 2 October).
- `revenue_one_day` semantic: Revenue on 2 October 2026 was €868.65. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_one_day` baseline: Revenue on 2 October 2026 was €868.65.
- `revenue_best_day` semantic: The highest-revenue day in October 2026 was 2026-10-01, with 981.69 EUR in revenue. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_best_day` baseline: The highest revenue day in October 2026 was 2026-10-01, with €981.69 in revenue (covering the period 1–31 October 2026).
- `net_revenue_one_day` semantic: Net revenue on 1 October 2026 was 964.19 EUR, covering that single day. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `net_revenue_one_day` baseline: Net revenue was €964.19 on 1 October 2026 (gross revenue €981.69 minus partner returns of €17.50).
- `net_revenue_total` semantic: Net revenue for 1 and 2 October 2026 combined was 1,825.59 EUR. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `net_revenue_total` baseline: The combined net revenue for 1 and 2 October 2026 is €1,825.59.
- `orders_one_day` semantic: On 1 October 2026, 15 orders were placed (cancelled ones included). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `orders_one_day` baseline: 15 orders were placed on 1 October 2026, including the 2 that were later cancelled.
- `cancelled_total` semantic: There were 5 cancelled orders over 1 and 2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cancelled_total` baseline: 5 orders were cancelled over 1 and 2 October 2026.
- `cancellation_rate` semantic: 16.7% of orders placed on 1–2 October 2026 were cancelled. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cancellation_rate` baseline: On 1–2 October 2026, 5 of 30 orders were cancelled, a cancelled share of 16.7%.
- `active_customers` semantic: On 2 October 2026, 9 distinct customers made at least one non-cancelled purchase. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `active_customers` baseline: 9 distinct customers bought on 2 October 2026.
- `returns_amount` semantic: €24.75 was returned to customers through partner returns from October 1–7, 2026 (early October). Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `returns_amount` baseline: €24.75 was returned to customers through partner returns (3 returns across 2 days) — covering 1–2 October 2026, the only days available in the data for early October 2026.
- `returns_one_day` semantic: On 1 October 2026 there were 2 partner returns, covering the single day 2026-10-01. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `returns_one_day` baseline: On 1 October 2026, there were **2 returns** (totaling €17.50 in returned value).
- `shipped_orders` semantic: 11 shipped orders overall. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `shipped_orders` baseline: 25 orders have shipped across the period from 2026-10-01 to 2026-10-02.
- `damaged_returns` semantic: Returns of damaged goods cost €12.5 across all available return data. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `damaged_returns` baseline: The tables track returns in EUR but not by reason, so returns specifically for damaged goods cannot be isolated. Total returns across all causes were €24.75 over 2026-10-01 to 2026-10-02.
- `revenue_germany` semantic: Revenue from customers in Germany on 1 October 2026 was €379.75, covering that single day. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_germany` baseline: Revenue from customers in Germany on 1 October 2026 was €379.75.
- `amsterdam_temperature` semantic: The semantic layer has no metric for average temperature or weather data. The available metrics cover lab sales, orders, cancellations, returns, bookings, ad spend, leads, and finance figures (revenue_eur, net_revenue_eur, returns_eur, orders_total, bookings, ad_spend_eur, etc.), but none relate to temperature or weather in Amsterdam.
- `amsterdam_temperature` baseline: The average temperature in Amsterdam on 1 October 2026 was 11.0°C.
- `cost_per_booking_total` semantic: Cost per booking was €130 over 1–2 October 2026. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cost_per_booking_total` baseline: Cost per booking was €130.00 (€390 total ad spend ÷ 3 bookings) across 1–2 October 2026.
- `cost_per_lead_search` semantic: Cost per lead from search campaigns in early October 2026 (October 1–7) was 46 EUR. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cost_per_lead_search` baseline: A search-campaign lead cost €46 on average (€230 ad spend across 5 leads) over Oct 1–2, 2026 — the full early-October period available in the data.
- `lead_to_booking_rate` semantic: The lead-to-booking rate for 1–2 October 2026 was 30%. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `lead_to_booking_rate` baseline: 30% of leads went on to book (3 bookings out of 10 leads) across 1 and 2 October 2026.
