# Semantic agent eval

Run 2026-11-01T02:37Z by `make agent-eval` (`services/semantic-agent`, semantic/PLAN.md SL-5), model `nvidia/nemotron-3.5-super-vl:free`, on `dbt/dev/fixture.sql`.
Each agent answers each question once through ADK's `LocalEvalService`; an answer is right when it carries the number the warehouse gives (`evals/questions.yaml`).

| | Semantic agent | Text-to-SQL baseline |
|---|---|---|
| Questions a metric covers (21) | 20 right, 21 with the expected metric, 21 quoting their freshness | 18 right |
| Questions no metric covers (1) | 1 said so | 1 right |
| All (22) | 21 | 19 |

| Question | Expected | Semantic | Metric | Freshness | Baseline |
|---|---|---|---|---|---|
| `revenue_total` What was our total revenue over 1 and 2 October 2026? | 1850.34 | ✓ | ✓ | ✓ | ✓ |
| `revenue_one_day` How much revenue did we make on 2 October 2026? | 868.65 | ✓ | ✓ | ✓ | ✓ |
| `revenue_best_day` Which day had the highest revenue in October 2026, and how much was it? | 981.69 | ✓ | ✓ | ✓ | ✓ |
| `net_revenue_one_day` What was net revenue on 1 October 2026, after partner returns? | 964.19 | ✓ | ✓ | ✓ | ✓ |
| `net_revenue_total` What is our net revenue for 1 and 2 October 2026 combined? | 1825.59 | ✓ | ✓ | ✓ | ✓ |
| `orders_one_day` How many orders were placed on 1 October 2026, cancelled ones included? | 15 | ✓ | ✓ | ✓ | ✓ |
| `cancelled_total` How many orders were cancelled over 1 and 2 October 2026? | 5 | ✓ | ✓ | ✓ | ✓ |
| `cancellation_rate` What share of our orders on 1 and 2 October 2026 was cancelled? | 0.166667 | ✗ | ✓ | ✓ | ✓ |
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
| `page_views_one_day` How many page views did customers make on our site on 1 October 2026? | 5 | ✓ | ✓ | ✓ | ✓ |
| `engaged_customers_week` How many customers did anything on our site or in the CRM in the week up to 3 October 2026? | 9 | ✓ | ✓ | ✓ | ✓ |
| `monthly_active_customers` How many monthly active customers did we have on 3 October 2026? | 10 | ✓ | ✓ | ✓ | ✓ |
| `view_to_cart_rate` What share of the site sessions that viewed a page on 1 October 2026 added something to the cart? | 0.8 | ✓ | ✓ | ✓ | ✗ |

## Answers

- `revenue_total` semantic: Total revenue was 1,850.34 EUR over 1–2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_total` baseline: Total revenue for 1–2 October 2026 was €1,850.34.
- `revenue_one_day` semantic: Revenue on 2 October 2026 was €868.65 (EUR), covering that single day. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_one_day` baseline: On 2 October 2026, revenue was **€868.65** for that single day.
- `revenue_best_day` semantic: The highest-revenue day in October 2026 was 2026-10-01, with 981.69 EUR of revenue (data for the month is only complete through 2026-10-03). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_best_day` baseline: The highest revenue day in October 2026 was 2026‑10‑01, with revenue of €981.69.
- `net_revenue_one_day` semantic: Net revenue on 1 October 2026 was EUR 964.19, covering that single day (revenue minus partner returns). Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `net_revenue_one_day` baseline: Net revenue on 1 October 2026 was €964.19, covering that single day after partner returns of €17.50.
- `net_revenue_total` semantic: Net revenue was €1,825.59 for 1–2 October 2026 combined. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `net_revenue_total` baseline: Net revenue was €1,825.59 combined for 1–2 October 2026 (€964.19 on Oct 1 and €861.40 on Oct 2).
- `orders_one_day` semantic: On 1 October 2026, there were 15 orders placed, cancelled included. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `orders_one_day` baseline: 15 orders were placed on 1 October 2026 (including the 2 cancelled ones).
- `cancelled_total` semantic: 5 cancelled orders over 1 and 2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cancelled_total` baseline: A total of 5 orders were cancelled (2 on 1 October and 3 on 2 October 2026).
- `cancellation_rate` semantic: On 1 October 2026, 13.3% of orders were cancelled, and on 2 October 2026, 20.0% were cancelled. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cancellation_rate` baseline: Across 1–2 October 2026, 5 of 30 orders were cancelled, a 16.67% cancelled share.
- `active_customers` semantic: 9 distinct customers bought from us on 2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `active_customers` baseline: 9 distinct customers made a purchase on 2 October 2026.
- `returns_amount` semantic: €24.75 went back to customers through partner returns from October 1–7, 2026. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `returns_amount` baseline: €24.75 was returned to customers, covering 2026-10-01 to 2026-10-02 (the only early-October dates available; 2026-10-01: €17.50, 2026-10-02: €7.25). Note: no "partner" dimension exists in the data; this is the total `returns_eur` from exposed.net_sales_daily for the available early-October 2026 period.
- `returns_one_day` semantic: We received 2 partner returns on 1 October 2026. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `returns_one_day` baseline: We recorded 2 returns on 1 October 2026 (from net sales, returns_count = 2; returns worth €17.50). Note: none of the warehouse tables contain a specific "partner returns" column; the closest available returns metric is net_sales_daily.returns_count.
- `shipped_orders` semantic: 11 orders have shipped, across the full period covered by the data (no date range specified). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `shipped_orders` baseline: 25 orders have shipped between 2026-10-01 and 2026-10-02.
- `damaged_returns` semantic: Returns of damaged goods cost 12.5 EUR, covering 2026-10-01. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `damaged_returns` baseline: The warehouse does not track returns by reason, so there is no “damaged goods” breakdown — only aggregate returns are recorded (`returns_eur`) in `exposed.net_sales_daily`. I can’t isolate the cost of damaged-goods returns from the available tables.
- `revenue_germany` semantic: Revenue from customers in Germany on 1 October 2026 was €379.75, covering that single day. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_germany` baseline: Revenue from customers in Germany on 1 October 2026 was €379.75, across 3 orders.
- `amsterdam_temperature` semantic: The semantic layer has no metric for weather or temperature—its metrics cover business measures like revenue, orders, bookings, ad spend, customers, and returns. There is no temperature metric, nor any dimension for city or weather, so I cannot answer this from the semantic layer. The closest available metrics are business ones such as `revenue_eur`, `orders_total`, `site_sessions`, and `customers
- `amsterdam_temperature` baseline: The average temperature in Amsterdam on 1 October 2026 was 11.0°C.
- `cost_per_booking_total` semantic: The cost per booking was EUR 130 over 1 and 2 October 2026. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cost_per_booking_total` baseline: The cost per booking was €130 over 1 and 2 October 2026.
- `cost_per_lead_search` semantic: A lead from search campaigns cost €46 in early October 2026 (October 1–7). Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cost_per_lead_search` baseline: A lead from search campaigns cost €46.00 in early October 2026 (€230 total ad spend across 5 leads on October 1–2, 2026).
- `lead_to_booking_rate` semantic: 30% of leads created on 1 and 2 October 2026 booked within 30 days. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `lead_to_booking_rate` baseline: 30% of the 10 leads from 1–2 October 2026 went on to book.
- `page_views_one_day` semantic: Customers made 5 page views on 1 October 2026. Late: customer_actions.silver has never been ready (deadline 36 h).
- `page_views_one_day` baseline: Customers made 5 page views on 1 October 2026.
- `engaged_customers_week` semantic: 9 customers did anything on the site or in the CRM in the 7 days ending 3 October 2026. Late: customer_actions.silver has never been ready (deadline 36 h).
- `engaged_customers_week` baseline: 9 customers did anything on the site or in the CRM during the week ending 3 October 2026 (27 Sep – 3 Oct 2026).
- `monthly_active_customers` semantic: We had 10 monthly active customers on 3 October 2026, counting distinct customers with any site or CRM action in the 28 days ending that day. Late: customer_actions.silver has never been ready (deadline 36 h).
- `monthly_active_customers` baseline: We had 10 monthly active customers on 3 October 2026 (the 28‑day engaged customer count for that date).
- `view_to_cart_rate` semantic: On 1 October 2026, 80% of site sessions that viewed a page added something to the cart. Late: customer_actions.silver has never been ready (deadline 36 h).
- `view_to_cart_rate` baseline: 60% of the site sessions that viewed a page added something to the cart on 1 October 2026.
