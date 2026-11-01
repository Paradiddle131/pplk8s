## 2026-11-01 — Semantic — a fiscal calendar on the time spine (#222)

- Done: `semantic.time_spine` carries `fiscal_quarter` and `fiscal_year` (each period's first day, for a fiscal year starting on 1 February: var `fiscal_year_start_month`, the dispatched `fiscal_period_start` macro), declared as custom granularities; `build_catalog.py` lists them with their descriptions (`custom_grains`), `list_metrics` gives them, and `query_metrics` takes `<time>__fiscal_quarter` and `__fiscal_year` as grains; `make semantic-check` and `make bigquery-emulator-check` compare signups by fiscal quarter of 2024 with SQL by hand (1, 4, 3 and 2, where calendar quarters give 4, 3 and 3); an eval question on fiscal Q3 revenue; SL-1 extended; dbt 0.7.37, semantic-agent 0.1.33.
- Evidence: see the PR for the gate counts.
- Decisions: semantic/PLAN.md SL-1 (the fiscal calendar; a 1 February start is a var, reversible).
- Open: offsets on custom grains are not supported yet in MetricFlow, so fiscal period-over-period waits.
