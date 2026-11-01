## 2026-11-01 — Semantic — query_metrics filters on time and numeric dimensions (#182)

- Done: a filter on a time dimension takes `=`, `!=`, `>`, `>=`, `<`, `<=` or `between` on ISO dates (rendered as `TimeDimension(..., 'day')`), one on a numeric dimension those and `in`, `not in` on plain decimal numbers; each value is parsed and written back from its parsed form, `between` takes the low end first, and a Jinja delimiter is refused for every type; `build_catalog.py` types a categorical dimension `numeric` when its column declares a numeric `data_type`; `order__amount` is the first; `make semantic-check` runs a signup-cohort and an amount filter, as the agent writes them, against SQL by hand; two eval questions; SL-2 updated; dbt 0.7.31, semantic-agent 0.1.27.
- Evidence: see the PR for the gate counts.
- Decisions: semantic/PLAN.md SL-2 (filters).
- Open: none.
