## 2026-11-01 — Semantic — customers get metrics of their own: signups, customers to date, signup-to-first-order rate (#219)

- Done: `signups` (simple, on `silver.customers` by signup day), `customers_to_date` (cumulative over all time, `period_agg: last`) and `signup_to_first_order_rate` (conversion on entity `customer`, base `signups`, conversion `orders_total`, 30-day window; `signups` and `orders_total` count `1`, since a conversion input must be COUNT, SUM(1) or COUNT_DISTINCT and a count over a column compiles to a SUM); `dev/fixture_weeks.sql` adds customers 11 to 30, signing up every third day of August and September 2026, seven of them ordering from 2026-10-04 (three within 30 days, one on the window's last day), so no earlier figure moves; `make semantic-check` compares the three with SQL by hand (3 of September's 9 signups convert; 30 customers by the end of September), `make bigquery-emulator-check` on the base fixture's 2024 signups; three eval questions; the brief's table, the glossary's signup cohort; 48 metrics; dbt 0.7.33, semantic-agent 0.1.29.
- Evidence: see the PR for the gate counts.
- Decisions: none.
- Open: none.
