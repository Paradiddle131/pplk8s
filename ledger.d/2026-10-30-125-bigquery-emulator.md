## 2026-10-30 — Semantic — the semantic path runs on a BigQuery emulator; the use-case map

- Done: Compose profile `bigquery` runs the goccy BigQuery emulator behind a standard-library shim (`platform/compose/bigquery-shim/`); `dbt/profiles.yml` gains a `bigquery_emulator` output; `make bigquery-emulator-check` copies the fixture's sources in from `dbt_dev`, runs `dbt build` of the semantic path and asserts the eight metrics equal gold and exposed on the emulator (#125). `semantic/PLAN.md` adds the use case (U1-U6, Map #135, its steps) and SL-7; `docs/semantic-layer-on-bigquery.md` marks what the emulator measured.
- Evidence: see the PR.
- Decisions: SL-7, emulator beside the Postgres warehouse, not in its place; the shim is a stated stopgap until the emulator handles `routines.list` and DDL statement types.
- Open: the use-case issues under Map #135.
