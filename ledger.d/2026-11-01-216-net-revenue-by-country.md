## 2026-11-01 — Semantic — net revenue and returns group by customer country (#216)

- Done: `slv_returns` carries `customer_id`, its order's customer from `slv_orders`, as a foreign `customer` entity, so `returns_eur` and `net_revenue_eur` group by `customer__country` as `revenue_eur` does; the singular hop `hop_slv_orders_to_slv_returns` holds each return's customer to its order's (62 hops); the dev fixture's three returns name real orders (they named `O-1` to `O-3`, which no order had); the "Customer country" glossary term names the two metrics; `make semantic-check` and `make bigquery-emulator-check` compare the three metrics by day and country with SQL by hand; an eval question on Germany's net revenue; dbt 0.7.30, semantic-agent 0.1.26.
- Evidence: see the PR for the gate counts.
- Decisions: none.
- Open: `tag:returns,tag:silver` now reads `silver.orders`, so the returns pipeline's silver build needs the sales pipeline's silver to exist.
