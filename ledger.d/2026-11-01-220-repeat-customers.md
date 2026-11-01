## 2026-11-01 — Semantic — repeat customers defined once, with a metric filter (#220)

- Done: `repeat_customers` and `revenue_repeat_customers_eur` (simple, on orders, filtered by `{{ Metric('orders_total', group_by=['customer']) }} >= 2` and non-cancelled) and `repeat_revenue_share` (ratio over `revenue_eur`); `make semantic-check` compares them by day and as one period with SQL by hand over 1 to 10 October (share 0.8657) and pins that a query's dates leave the inner order count unlimited (2 October alone: 868.65, not 467.90); an eval question; the brief's table; a semantic/PLAN.md lesson; 51 metrics; dbt 0.7.34, semantic-agent 0.1.30.
- Evidence: see the PR for the gate counts.
- Decisions: none; the filter lives in the YAML, never in the agent's tool (SL-2).
- Open: the emulator check does not run the metric filter yet (the six-week fixture is not on the emulator).
