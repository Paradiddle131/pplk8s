## 2026-11-01 — Semantic — SourceStale says "was never loaded" for an empty landed table (#224)

- Done: the source-freshness hook records no newest load when dbt reports year 1 for an empty table (it wrote `1-01-01`, which Postgres read as 2001-01-01); `SourceStale`'s summary says "was never loaded" when the age passes 1e9 s, as `DataProductLate` does; a promtool case on a 2026 clock; `make source-freshness-check` empties one table and expects `error` with no newest load; runbook § 13; dbt image 0.7.28, semantic-agent 0.1.24 (both carry the macros).
- Evidence: see the PR for the gate counts.
- Decisions: none.
- Open: none.
