## 2026-11-01 — Semantic — query_metrics groups by a date part and by an entity (#221)

- Done: `query_metrics` builds MetricFlow's typed group-by parameters from checked names: a time grain (`metric_time__week`), a date part (`<time>__extract_dow` and year, quarter, month, day, doy; ISO weekdays), a dimension, or an entity the catalog lists for every metric asked (`campaign`, `customer`: one row per id); order-bys are typed too; `build_catalog.py` lists each metric's entities and `describe_metric` shows them; `tests/e2e/lib/mf_date_part.py` runs a date-part query as the agent builds it, which `make semantic-check` compares with gold over six whole weeks and `make bigquery-emulator-check` on the emulator (BigQuery's `DAYOFWEEK` starts on Sunday); two eval questions (best weekday, top three campaigns by spend); the MetricFlow surface test pins the typed parameters; SL-2 updated; dbt 0.7.32, semantic-agent 0.1.28.
- Evidence: see the PR for the gate counts.
- Decisions: semantic/PLAN.md SL-2 (group-bys). An entity group-by keeps the 200-row cap and no lower default: its rows are ids, and "top N" is an order and a limit the model sends.
- Open: none.
