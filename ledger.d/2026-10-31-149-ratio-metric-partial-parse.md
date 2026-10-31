## 2026-10-31 — Semantic — The ratio metric moves off slv_orders, so a partial parse no longer duplicates it (#149)

- Done: `cancellation_rate` moves from `slv_orders`' metrics in `dbt/models/silver/schema.yml` to `models/semantic/semantic.yml` (same name, label, description, numerator and denominator); both files' headers say metrics over other metrics live there. After a full parse, an edit of `slv_orders` then `dbt parse` no longer fails with `dbt found two metrics with the name "cancellation_rate"`. The agent's test catalog fixture is refreshed (three glossary descriptions had drifted). The profile's known-condition line is gone. dbt image 0.7.10, semantic-agent 0.1.8.
- Evidence: see the PR.
- Decisions: none; a lesson in semantic/PLAN.md § 6.
- Open: none.
