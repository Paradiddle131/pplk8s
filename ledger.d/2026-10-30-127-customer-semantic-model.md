## 2026-10-30 — Semantic — Metrics group by customer country and signup cohort (#127)

- Done: `slv_customers` becomes the `customers` semantic model (primary entity `customer`, dimensions `country` and `signup_date`), with no metric of its own, so every orders metric groups and filters by `customer__country` and `customer__signup_date__month` through the entity `orders` already declared. The eval's `revenue_germany` now expects `revenue_eur` instead of a decline. `semantic-check.sh` compares the orders metrics by day and country with `exposed.sales_by_country_daily` and revenue by signup month with a direct join of silver. dbt image 0.7.5 and semantic-agent 0.1.2 (both carry the dbt project).
- Evidence: see the PR.
- Decisions: none; a time dimension with MetricFlow's month grain is the cohort, rather than a derived `signup_month` column.
- Open: none.
