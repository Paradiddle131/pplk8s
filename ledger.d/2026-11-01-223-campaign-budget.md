## 2026-11-01 — Semantic — a semi-additive balance: each campaign's budget left in the month (#223)

- Done: EL Factory's synthetic marketing source gains `campaign_budgets` (one snapshot per campaign per day: the month's budget by channel and what is left after the day's spend, from the same seeded spend as `ad_spend`), in the `marketing` pipeline's catalog, so `marketing_elt` extracts it with no DAG change; dbt `ds_source.synthetic_campaign_budgets` (freshness as the daily sources), `brz_synthetic_campaign_budgets`, `slv_campaign_budgets` with its hop, and `remaining_budget_eur` with `non_additive_dimension {name: snapshot_date, window_agg: max, group_by: [campaign]}`; both dev fixtures carry snapshots consistent with their spend; `make semantic-check` compares it by month with the month-end snapshots by hand (September 4130.00, the naive sum of days 217230.00), `make bigquery-emulator-check` by day and over two days; `make source-freshness-check` counts 17 landed tables; an eval question; SL-8 extended; el-factory 0.7.8, dbt 0.7.38, semantic-agent 0.1.34.
- Evidence: see the PR for the gate counts.
- Decisions: semantic/PLAN.md SL-8 (the budget snapshot).
- Open: none.
