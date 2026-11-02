## 2026-11-02 — Semantic — gcp-image-check gets a database of its own

- Done: `tests/e2e/gcp-image-check.sh` recreates a Postgres database `gcp_image_check` each run, loads `dbt/dev/fixture.sql` alone into it and copies that one into the BigQuery emulator; it no longer reads or resets `dbt_dev`.
- Why: after `tests/e2e/agent-fixture.sh`, `dbt_dev` also holds `fixture_weeks.sql`'s six weeks (218 orders, 142 ad-spend, 141 budget and 211 lead rows copied), and the emulator's hops over those four tables timed out at 600 s, about 45 minutes a run (#287).
- Evidence: after `agent-fixture.sh` (218 orders left in `dbt_dev`), `make gcp-image-check` PASS in 12 minutes: `gcp_image_check` holds 31 orders, dbt build PASS=173 ERROR=0, the 31 hops, MetricFlow 2 days; `dbt_dev` still holds 218 orders afterwards. `make verify` exit 0 (pytest 32, 246, 204, 153, 32 passed; every image built) on cloud.
- Decisions: none.
- Open: none.
