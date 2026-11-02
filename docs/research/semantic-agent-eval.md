# Semantic agent eval

Run 2026-11-02T00:23Z by `make agent-eval` (`services/semantic-agent`, semantic/PLAN.md SL-5), model `nvidia/nemotron-3.5-super-vl:free`, on `dbt/dev/fixture.sql` and `dbt/dev/fixture_weeks.sql`.
Each agent answers each case once through ADK's `LocalEvalService`, the turns of a conversation in one session; an answer is right when it carries the number the warehouse gives (`evals/questions.yaml`), quotes the metric's definition when asked how a figure was computed, and asks which meaning (or gives each) when a term has more than one.

| | Semantic agent | Text-to-SQL baseline |
|---|---|---|
| Questions a metric covers (47) | 47 right, 47 with the expected metric, 47 quoting their freshness | 31 right |
| Questions no metric covers (2) | 2 said so | 1 right |
| Follow-ups, definitions and ambiguous terms (7) | 7 right | 4 right |
| All (56) | 56 | 36 |

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
| `returns_amount` How much money went back to customers through partner returns in early October 2026? | 89.75 | ✓ | ✓ | ✓ | ✓ |
| `returns_one_day` How many partner returns did we get on 1 October 2026? | 2 | ✓ | ✓ | ✓ | ✗ |
| `shipped_orders` How many orders have shipped? | 86 | ✓ | ✓ | ✓ | ✗ |
| `damaged_returns` How much did returns of damaged goods cost us? | 62.5 | ✓ | ✓ | ✓ | ✗ |
| `revenue_germany` What was our revenue from customers in Germany on 1 October 2026? | 379.75 | ✓ | ✓ | ✓ | ✓ |
| `net_revenue_germany` What was our net revenue from customers in Germany on 1 October 2026, after returns? | 367.25 | ✓ | ✓ | ✓ | ✗ |
| `revenue_signup_cohort` What revenue did customers who signed up in August or September 2024 bring in on 1 October 2026? | 312 | ✓ | ✓ | ✓ | ✗ |
| `orders_over_100` How many orders of more than 100 EUR were placed on 1 and 2 October 2026? | 6 | ✓ | ✓ | ✓ | ✗ |
| `best_weekday_revenue` Over the six weeks from Monday 17 August to Sunday 27 September 2026, which day of the week brought in the most revenue, and how much? | 2423.75 | ✓ | ✓ | ✓ | ✓ |
| `top_campaigns_by_spend` Which three campaigns spent the most on ads in September 2026, and how much did the top one spend? | 3870 | ✓ | ✓ | ✓ | ✓ |
| `signups_september` How many new customers signed up in September 2026? | 9 | ✓ | ✓ | ✓ | ✗ |
| `customers_to_date` How many customers had signed up in total by the end of September 2026? | 30 | ✓ | ✓ | ✓ | ✗ |
| `signup_to_first_order_rate` What share of the customers who signed up in September 2026 placed an order within 30 days of signing up? | 0.333333 | ✓ | ✓ | ✓ | ✗ |
| `repeat_revenue_share` What share of our revenue from 1 to 10 October 2026 came from repeat customers? | 0.865721 | ✓ | ✓ | ✓ | ✗ |
| `return_rate_september` What share of the orders placed in September 2026 were returned? | 0.0166667 | ✓ | ✓ | ✓ | ✗ |
| `damaged_return_share` Of the returns of orders placed from August to October 2026, what share were returned as damaged? | 0.5 | ✓ | ✓ | ✓ | ✗ |
| `average_order_value` What was our average order value on 1 October 2026? | 75.5146 | ✓ | ✓ | ✓ | ✗ |
| `median_order_value` What was the median order value on 1 October 2026? | 45 | ✓ | none | none | ✗ |
| `revenue_fiscal_q3` What was our revenue in the third quarter of fiscal 2026? | 19793.6 | ✓ | ✓ | ✓ | ✓ |
| `budget_left_end_of_september` How much of our campaigns' budget was left at the end of September 2026? | 4130 | ✓ | ✓ | ✓ | ✗ |
| `amsterdam_temperature` What was the average temperature in Amsterdam on 1 October 2026? | 11 | ✓ | none | none | ✓ |
| `cost_per_booking_total` What was our cost per booking over 1 and 2 October 2026? | 130 | ✓ | ✓ | ✓ | ✓ |
| `cost_per_lead_search` How much did a lead from search campaigns cost us in early October 2026? | 46 | ✓ | ✓ | ✓ | ✓ |
| `lead_to_booking_rate` What share of our leads from 1 and 2 October 2026 went on to book? | 0.3 | ✓ | ✓ | ✓ | ✓ |
| `page_views_one_day` How many page views did customers make on our site on 1 October 2026? | 5 | ✓ | ✓ | ✓ | ✓ |
| `engaged_customers_week` How many customers did anything on our site or in the CRM in the week up to 3 October 2026? | 9 | ✓ | ✓ | ✓ | ✓ |
| `monthly_active_customers` How many monthly active customers did we have on 3 October 2026? | 10 | ✓ | ✓ | ✓ | ✓ |
| `view_to_cart_rate` What share of the site sessions that viewed a page on 1 October 2026 added something to the cart? | 0.8 | ✓ | ✓ | ✓ | ✗ |
| `outreach_messages_sent` How many outreach messages did we send to partner contacts from 1 to 3 October 2026? | 6 | ✓ | ✓ | ✓ | ✓ |
| `outreach_reply_rate` What share of the outreach messages we sent from 1 to 3 October 2026 got a reply? | 0.666667 | ✓ | ✓ | ✓ | ✓ |
| `partners_engaged_one_day` How many partners replied to our outreach on 2 October 2026? | 2 | ✓ | ✓ | ✓ | ✗ |
| `candidates_in_interview_as_of` How many candidates were in the interview stage on 4 October 2026? | 1 | ✓ | ✓ | ✓ | ✓ |
| `time_to_hire` On average, how many days did it take to hire a candidate, over everyone hired in October 2026? | 6.0833 | ✓ | ✓ | ✓ | ✓ |
| `calls_about_returns` How many of our customer calls on 1 and 2 October 2026 were about returns? | 3 | ✓ | ✓ | ✓ | ✓ |
| `objection_rate` In what share of our customer calls on 1 and 2 October 2026 did the customer raise an objection? | 0.333333 | ✓ | ✓ | ✓ | ✓ |
| `revenue_wow_growth` By what percentage did revenue in the week starting Monday 14 September 2026 grow over the week before? | 0.326533 | ✓ | ✓ | ✓ | ✓ |
| `bookings_wow_growth` How much did bookings grow in the week of 14 September 2026 compared with the previous week? | 0.272727 | ✓ | ✓ | ✓ | ✓ |
| `leads_wow_growth` What was the week-over-week growth in leads for the week starting 14 September 2026? | 0.206897 | ✓ | ✓ | ✓ | ✓ |
| `revenue_mtd` What was our revenue month to date on 15 September 2026? | 5668.75 | ✓ | ✓ | ✓ | ✓ |
| `leads_mtd` How many leads came in during September 2026 up to and including the 10th, month to date? | 42 | ✓ | ✓ | ✓ | ✓ |

A conversation runs its turns in one session; a column no turn of a case applies to says none.

| Case | Expected | Semantic: numbers | Definition | Asks which | Metric | Freshness | Baseline: numbers | Definition | Asks which |
|---|---|---|---|---|---|---|---|---|---|
| `followup_by_country` What was our total revenue over 1 and 2 October 2026? → And broken down by customer country, how much of it came from Germany? | 1850.34 → 410.75 | ✓ | none | none | ✓ | ✓ | ✓ | none | none |
| `followup_day_before` How much revenue did we make on 2 October 2026? → And on the day before? | 868.65 → 981.69 | ✓ | none | none | ✓ | ✓ | ✓ | none | none |
| `followup_switch_metric` How many orders were placed on 1 October 2026, cancelled ones included? → What was the net revenue that day, after partner returns? | 15 → 964.19 | ✓ | none | none | ✓ | ✓ | ✓ | none | none |
| `followup_how_computed` What was net revenue on 1 October 2026, after partner returns? → How was that number computed? | 964.19 → – | ✓ | ✓ | none | ✓ | ✓ | ✓ | ✗ | none |
| `followup_rate_how_computed` What share of our orders on 1 and 2 October 2026 was cancelled? → How did you calculate that rate? | 0.166667 → – | ✓ | ✓ | none | ✓ | ✓ | ✓ | ✗ | none |
| `ambiguous_sales` What were our sales on 1 October 2026? → I mean net sales, after returns. | 981.69 / 964.19 → 964.19 | ✓ | none | ✓ | ✓ | ✓ | ✓ | none | ✓ |
| `ambiguous_customers` How many customers did we have in September 2026? | 9 / 10 / 30 | none | none | ✓ | none | ✓ | none | none | ✗ |

## Answers

- `revenue_total` semantic: Total revenue was €1,850.34 over 1–2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_total` baseline: Total revenue was €1,850.34 over 1–2 October 2026.
- `revenue_one_day` semantic: Revenue on 2 October 2026 was €868.65 (EUR), covering that single day. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_one_day` baseline: Revenue on 2 October 2026 was €868.65 EUR (single day).
- `revenue_best_day` semantic: The highest revenue day in October 2026 was 2026‑10‑01, with EUR 981.69 in revenue. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_best_day` baseline: October 1, 2026 had the highest revenue at €981.69, covering October 1–31, 2026.
- `net_revenue_one_day` semantic: Net revenue on 1 October 2026, after partner returns, was €964.19 (revenue €981.69 minus returns €17.50 across 2 returns). Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `net_revenue_one_day` baseline: Net revenue on 1 October 2026 was €964.19.
- `net_revenue_total` semantic: Net revenue was **1,825.59 EUR** for 1–2 October 2026 combined. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `net_revenue_total` baseline: Combined net revenue for 1–2 October 2026 was 1,825.59 EUR.
- `orders_one_day` semantic: On 1 October 2026, 15 orders were placed (cancelled ones included). This covers the single day of 2026-10-01. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `orders_one_day` baseline: 15 orders were placed on 1 October 2026, including 2 cancelled ones.
- `cancelled_total` semantic: 5 cancelled orders over 1 and 2 October 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cancelled_total` baseline: 5 orders were cancelled over 1 and 2 October 2026.
- `cancellation_rate` semantic: On 1–2 October 2026, 16.7% of orders were cancelled. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cancellation_rate` baseline: About 16.7% of orders were cancelled on 1–2 October 2026.
- `active_customers` semantic: On 2 October 2026, 9 distinct customers bought from us (at least one non-cancelled order that day). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `active_customers` baseline: 9 distinct customers bought from us, covering the single day of 2 October 2026.
- `returns_amount` semantic: €89.75 went back to customers through partner returns from October 1–7, 2026. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `returns_amount` baseline: Partner returns returned **89.75 EUR** to customers between **1 October 2026 and 7 October 2026** (early October 2026).
- `returns_one_day` semantic: On 1 October 2026 we received 2 partner returns, covering that single day. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `returns_one_day` baseline: The available tables do not contain a "partner returns" metric for 1 October 2026. The partner_outreach_daily table tracks partner outreach (messages sent/replied, partners engaged) but has no returns column, and net_sales_daily's returns_count/returns_eur are general sales returns, not partner-specific.
- `shipped_orders` semantic: 86 orders have shipped, covering all time in the data (no period was specified). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `shipped_orders` baseline: 197 orders have shipped, covering 54 days from 2026‑08‑17 to 2026‑10‑10.
- `damaged_returns` semantic: Returns of damaged goods cost €62.50 over all available data (returns recorded up to 2026‑10‑03). Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `damaged_returns` baseline: Returns of goods cost a total of €89.75 over the 54-day period from 2026-08-17 to 2026-10-10. (Note: the data tracks returns in euros generally; no separate "damaged goods" category is available.)
- `revenue_germany` semantic: Revenue from customers in Germany on 1 October 2026 was 379.75 EUR, covering that single day. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_germany` baseline: Revenue from customers in Germany on 1 October 2026 was €379.75.
- `net_revenue_germany` semantic: Net revenue from customers in Germany on 1 October 2026 was €367.25 (revenue minus partner returns, i.e. finance's net sales). Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `net_revenue_germany` baseline: Net revenue from customers in Germany on 1 October 2026 was €379.75.
- `revenue_signup_cohort` semantic: Customers who signed up in August or September 2024 generated €312.00 in revenue on 1 October 2026 (revenue = sum of non-cancelled order amounts for that signup cohort on that day). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_signup_cohort` baseline: The warehouse does not store revenue broken down by individual customer on a daily basis, so the revenue from customers who signed up in August or September 2024 on 1 October 2026 cannot be determined.
- `orders_over_100` semantic: There were **6 orders** of more than 100 EUR placed on **1 and 2 October 2026**. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `orders_over_100` baseline: The warehouse only stores daily aggregates (order count and total revenue), not individual order values, so the number of orders over 100 EUR cannot be determined. For context, on 1–2 October 2026 there were 15 orders each day (30 total) with revenue of €981.69 and €868.65 respectively (average order ≈ €65 and €58).
- `best_weekday_revenue` semantic: Sunday brought in the most revenue, EUR 2,423.75, over Monday 17 August to Sunday 27 September 2026 (six weeks). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `best_weekday_revenue` baseline: Sunday brought in the most revenue, €2,423.75, across the six weeks from Monday 17 August to Sunday 27 September 2026.
- `top_campaigns_by_spend` semantic: The top three campaigns by ad spend in September 2026 were "Search NL always-on" at 3,870.00 EUR, "Social TR spring" at 2,100.00 EUR, and "Newsletter monthly" at 300.00 EUR, covering 2026-09-01 to 2026-09-30; the top campaign spent 3,870.00 EUR. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `top_campaigns_by_spend` baseline: The three channels with the highest ad spend in September 2026 were **search** (€3,870.00), **social** (€2,100.00), and **email** (€300.00). The top spender, search, spent €3,870.00.
- `signups_september` semantic: 9 new customers signed up in September 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `signups_september` baseline: 0 new customers signed up in September 2026.
- `customers_to_date` semantic: 30 customers had signed up in total by the end of September 2026 (covering all signups up to 2026‑09‑30). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `customers_to_date` baseline: 10 customers by the end of September 2026.
- `signup_to_first_order_rate` semantic: 33.3% of customers who signed up in September 2026 placed their first order within 30 days of signing up (the signup day and the 29 after it). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `signup_to_first_order_rate` baseline: Cannot be determined from these tables. No customer signup/registration date is recorded (gold.customer_lifetime only holds first_order_date), and zero customers have a first order in September 2026, so there is no valid denominator to compute a share.
- `repeat_revenue_share` semantic: From1 to 10 October 2026, **86.57% of revenue** came from repeat customers (a repeat-revenue share of 0.8657). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `repeat_revenue_share` baseline: The available tables do not break down revenue by repeat versus new customers for 1–10 October 2026, so the share of revenue from repeat customers cannot be calculated from the data.
- `return_rate_september` semantic: In September 2026, the return rate was 1.67% (about 1 in 60 orders placed that month were returned). Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `return_rate_september` baseline: 0% — 0 of the 120 orders placed in September 2026 were returned (covering 2026-09-01 through 2026-09-30).
- `damaged_return_share` semantic: 50% of returns of orders placed from August 1 to October 31, 2026 were returned as damaged. Fresh: returns.silver is ready up to 2026-10-03T00:00Z.
- `damaged_return_share` baseline: The available tables cannot answer this question. None of them record a return reason (e.g., "damaged") — return data exists only as aggregate counts/amounts in exposed.net_sales_daily, and customer action types contain no return or damage category. Therefore the share of returns from August–October 2026 that were damaged cannot be computed from these tables.
- `average_order_value` semantic: The average order value on 1 October 2026 was €75.51 (EUR), covering that single day. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `average_order_value` baseline: Average order value was €65.45 on 1 October 2026.
- `median_order_value` semantic: The semantic layer does not have a median order value metric available for this warehouse — `median_order_value_eur` is defined only for BigQuery and is not accessible here. The closest available metric is **average order value (EUR)** (`average_order_value_eur`), which measures the average amount of a non-cancelled order over the period asked, but it is an average, not a median. If you'd like, I 
- `median_order_value` baseline: The warehouse tables only contain daily aggregated order counts (e.g., `orders_total`) by `order_date`, not individual order amounts. There's no per-order value column in `gold.daily_sales`, `exposed.net_sales_daily`, or related tables, so a median order value for 1 October 2026 cannot be computed from the available data.
- `revenue_fiscal_q3` semantic: Revenue was €19,793.59 for fiscal Q3 2026 (2026-08-01 to 2026-10-31). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_fiscal_q3` baseline: Revenue for Q3 fiscal 2026 (assuming a fiscal year starting February 1, so Q3 = August–October) was €19,793.59. This covers the available data from August 17 to October 10, 2026 (54 days); full-quarter data for Aug 1–16 and Oct 11–31 is not in the warehouse.
- `budget_left_end_of_september` semantic: At the end of September 2026, €4,130.00 of campaign budget was left across all campaigns. Freshness: Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `budget_left_end_of_september` baseline: The available tables do not contain any campaign budget or remaining-budget data (no `budget` or `campaign` columns exist). While `marketing_daily` and `channel_performance_daily` track `ad_spend_eur`, there is no allocated budget figure to subtract spend from, so the budget left at the end of September 2026 cannot be determined.
- `amsterdam_temperature` semantic: The semantic layer has no metric for temperature or weather in Amsterdam — its metrics cover business measures like ad spend, bookings, orders, revenue, returns, and customers. There is no closest metric for this question either. Answer: The semantic layer has no such metric.
- `amsterdam_temperature` baseline: The average temperature in Amsterdam on 1 October 2026 was 11.0°C.
- `cost_per_booking_total` semantic: Cost per booking was €130.00 over 1–2 October 2026. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cost_per_booking_total` baseline: Cost per booking was €130.00 over 1–2 October 2026, based on €390.00 total ad spend across 3 bookings.
- `cost_per_lead_search` semantic: The cost per lead from search campaigns was 46.0 EUR over 2026-10-01 to 2026-10-07. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `cost_per_lead_search` baseline: A search-campaign lead cost €46.00 on average in early October 2026 (€230 ad spend ÷ 5 leads), covering 1–2 October 2026 — the only early-October dates in the data (€43.33 on Oct 1, €50.00 on Oct 2).
- `lead_to_booking_rate` semantic: The lead-to-booking rate for leads created on 1–2 October 2026 is 0.30 (30 %), covering those two days. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `lead_to_booking_rate` baseline: 30% of leads booked, covering 1–2 October 2026.
- `page_views_one_day` semantic: 5 page views on 1 October 2026. Late: customer_actions.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `page_views_one_day` baseline: Customers made 5 page views on the site on 1 October 2026.
- `engaged_customers_week` semantic: 9 distinct customers did anything on the site or in the CRM in the week ending 3 October 2026 (27 September–3 October 2026). Late: customer_actions.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `engaged_customers_week` baseline: 9 customers did anything on the site or in the CRM during the week through 3 October 2026 (27 September–3 October 2026).
- `monthly_active_customers` semantic: Monthly active customers (distinct customers with any site or CRM action in the 28 days ending on that day) on 3 October 2026: **10 customers**, covering 6 September through 3 October 2026. Late: customer_actions.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `monthly_active_customers` baseline: We had 10 monthly active customers (28-day engaged customers) on 3 October 2026.
- `view_to_cart_rate` semantic: 0.8 (80%) of site sessions that viewed a page on 1 October 2026 added something to the cart — the view-to-cart rate for 1 October 2026, counting sessions with a page view that added to cart on the page view's day or the day after. Late: customer_actions.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `view_to_cart_rate` baseline: 60% — 3 of the 5 site sessions added something to the cart on 1 October 2026 (cart_sessions ÷ site_sessions = 3 ÷ 5).
- `outreach_messages_sent` semantic: We sent **6 outreach messages** to partner contacts from 1 to 3 October 2026. Late: partner_outreach.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `outreach_messages_sent` baseline: We sent 6 outreach messages to partner contacts from 1 to 3 October 2026.
- `outreach_reply_rate` semantic: From 1 to 3 October 2026, about 66.7% of the outreach messages sent got a reply (a reply rate of 0.667 over that three-day period). Late: partner_outreach.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `outreach_reply_rate` baseline: 66.7% of outreach messages received a reply from 1 to 3 October 2026.
- `partners_engaged_one_day` semantic: On 2 October 2026, **2 partners** replied to outreach. This covers the single day of 2026-10-02, counting distinct partners with at least one reply from their contacts. Late: partner_outreach.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `partners_engaged_one_day` baseline: 1 partner replied to outreach on 2 October 2026.
- `candidates_in_interview_as_of` semantic: On 4 October 2026, 1 candidate was in the interview stage (a count of candidates, for that single day). Late: recruitment.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `candidates_in_interview_as_of` baseline: On 4 October 2026, there was 1 candidate in the interview stage.
- `time_to_hire` semantic: On average, it took 6.08 days to hire a candidate, covering everyone hired from October 1 through October 31, 2026. Late: recruitment.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `time_to_hire` baseline: It took an average of 6.08 days to hire a candidate, across the 2 people hired in October 2026 (hires occurred on October 2 and October 3).
- `calls_about_returns` semantic: On 1 and 2 October 2026, 3 of your customer calls were about returns. Late: call_transcripts.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `calls_about_returns` baseline: 3 customer calls were about returns on 1 and 2 October 2026 (2 on 1 October, 1 on 2 October).
- `objection_rate` semantic: On 1–2 October 2026, the customer raised an objection in about 33.3% of labelled customer calls (objection rate 0.3333333333333333, i.e. calls with an objection over calls labelled over that period). Late: call_transcripts.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `objection_rate` baseline: On 1–2 October 2026, customers raised an objection in 1/3 (about 33.3%) of the 12 labelled customer calls (4 objection calls).
- `revenue_wow_growth` semantic: Revenue grew by about 32.7% (a growth share of 0.3265) in the week starting Monday 14 September 2026 over the week before (7–13 September 2026). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_wow_growth` baseline: Revenue grew by 32.65% in the week starting Monday 14 September 2026 compared with the previous week (7–13 September 2026).
- `bookings_wow_growth` semantic: Bookings grew by approximately 27.3% (0.2727 as a share) in the week of 14 September 2026 compared with the previous week. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `bookings_wow_growth` baseline: Bookings grew by 3 (from 11 to 14), a +27.27% increase, for the week of 14–20 September 2026 versus the previous week of 7–13 September 2026.
- `leads_wow_growth` semantic: For the week starting 14 September 2026, week-over-week leads growth was about 0.207 (20.7%), meaning leads rose by roughly 20.7% compared with the previous week. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `leads_wow_growth` baseline: Leads increased by 20.7% week-over-week, rising from 29 leads in the week starting 7 September 2026 to 35 leads in the week starting 14 September 2026.
- `revenue_mtd` semantic: Revenue month to date on 15 September 2026 was €5,668.75, covering 1 September through 15 September 2026. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `revenue_mtd` baseline: Revenue month to date on 15 September 2026 was €5,668.75, covering 1–15 September 2026 (15 days).
- `leads_mtd` semantic: 42 leads came in during September 2026 month to date up to and including the 10th. Late: marketing.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `leads_mtd` baseline: 42 leads were recorded from September 1 through September 10, 2026.
- `followup_by_country` semantic: Total revenue was €1,850.34 over 1–2 October 2026 (non-cancelled orders). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline. → €410.75 of that revenue came from Germany (customer country DE) over 1–2 October 2026 (non-cancelled orders). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `followup_by_country` baseline: Total revenue was €1,850.34 over 1 and 2 October 2026. → €410.75 came from Germany over 1 and 2 October 2026.
- `followup_day_before` semantic: Revenue on 2 October 2026 was EUR 868.65, covering that single day (sum of non-cancelled orders). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline. → Revenue on 1 October 2026 was EUR 981.69, covering that single day (sum of non-cancelled orders). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `followup_day_before` baseline: We made €868.65 in revenue on 2 October 2026. → We made €981.69 in revenue on 1 October 2026.
- `followup_switch_metric` semantic: On 1 October 2026, **15 orders** were placed (cancelled ones included), covering that single day. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline. → On 1 October 2026, net revenue after partner returns was **964.19 EUR**, covering that single day. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `followup_switch_metric` baseline: 15 orders were placed on 1 October 2026 (including the 2 cancelled ones). → On 1 October 2026, net revenue was €964.19 after partner returns.
- `followup_how_computed` semantic: Net revenue on 1 October 2026 was EUR 964.19, covering revenue minus partner returns (finance's net sales) for that single day. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline. → The metric behind it is defined as: **"Revenue minus partner returns (finance's net sales)."** In plain words, the query summed the amounts of all non-cancelled orders placed on 1 October 2026 (that is revenue), summed the amounts of partner returns recorded on that same day, and subtracted the returns from revenue to give net revenue.
- `followup_how_computed` baseline: Net revenue on 1 October 2026 was €964.19 (after €17.50 in partner returns from €981.69 gross revenue). → It was computed as gross revenue minus partner returns: €981.69 − €17.50 = €964.19.
- `followup_rate_how_computed` semantic: 16.7% of orders were cancelled over 1–2 October 2026 (one-sixth of all orders placed on those two days). Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline. → The metric is “Cancellation rate,” defined as “Share of orders cancelled.” In plain terms, the query summed cancelled orders on 1–2 October 2026, divided that by all orders placed on those same two days, and reported the ratio as a share.
- `followup_rate_how_computed` baseline: 16.67% of orders were cancelled on 1 and 2 October 2026. → I summed the cancelled orders and total orders from `gold.daily_sales` for 1–2 October 2026, then divided cancelled by total and multiplied by 100: (5 cancelled ÷ 30 total) × 100 = 16.67%.
- `ambiguous_sales` semantic: On 1 October 2026, gross revenue (non-cancelled orders) was €981.69 and net revenue (revenue minus partner returns) was €964.19, both in EUR for that single day. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline. → Net sales (revenue minus partner returns) were €964.19 in EUR on 1 October 2026. Fresh: returns.silver is ready up to 2026-10-03T00:00Z. Late: sales.silver is ready only up to 2026-10-03T00:00Z, older than its 36 h deadline.
- `ambiguous_sales` baseline: On 1 October 2026, net sales were €964.19 (from 15 orders generating €981.69 in gross revenue). → Net sales after returns on 1 October 2026 were €964.19.
- `ambiguous_customers` semantic: Here are the three possible readings of "customers" for September 2026, each under its own metric: - **Signups (new customers)**: 9 customers signed up during September 2026. - **Active customers**: 10 distinct customers placed at least one non-cancelled order during September 2026. - **Customers to date**: 30 customers had signed up by the end of September 2026 (cumulative running total). Late: s
- `ambiguous_customers` baseline: We had **10 customers** active during **September 2026**.
