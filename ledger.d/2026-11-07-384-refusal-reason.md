## 2026-11-07 — Semantic track — a warehouse refusal reaches the model as its reason (#384)

- Done: `semantic_agent.metrics.refusal_reason` joins dbt's "Database Error" heading with the warehouse's message on the next line, so `query_metrics` answers e.g. "the semantic layer rejected the query: Database Error: Syntax error: Unexpected keyword ORDER at [15:17]"; MetricFlow's own validation errors keep their first line.
- Evidence: `tests/test_metrics.py` 91 passed, one new test raising a `DbtDatabaseError` through `metrics.run`; ruff clean.
- Held: merged into the semantic bet's train only between passes (after the MetricFlow arms' extended hard set k = 3), so no pass mixes the two error texts; refusals were 0.1-1.2% of the MetricFlow logs' lines.
