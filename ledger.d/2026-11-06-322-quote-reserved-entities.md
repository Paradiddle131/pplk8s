## 2026-11-06 — Semantic track — the agent's MetricFlow queries on BigQuery quote reserved-word names (#322)

- Done: `quote_reserved` moved from `dbt/scripts/build_governed.py` into `services/semantic-agent/src/semantic_agent/bigquery_sql.py` (standard library only), now skipping string literals, backticked names and comments.
  The agent's `metrics.engine()` gives MetricFlow a `QuotingSqlClient` when dbt's target is BigQuery, so the SQL that runs, `explain` and the audit are one quoted statement.
  `build_governed.py` loads the same module by its path (`SEMANTIC_AGENT_SRC`, set by `tests/e2e/governed-models.sh`), because the agent's package imports ADK.
  `tests/test_bigquery_sql.py` covers the quoting and the engine wiring; `bigquery_sql_rules.py`'s `RESERVED_NAME` rule is unchanged.
- Evidence: on the lab project (`DBT_TARGET=gcp`), before the fix the dry run of MetricFlow's SQL for `returns_count` by `order__status` was refused with `Syntax error: Unexpected keyword ORDER at [15:17]`, and `tools.query_metrics` returned `the semantic layer rejected the query: Database Error` (job `99655bd1`, nothing billed).
  After the fix the dry run read 4,687 bytes, and `query_metrics` answered `shipped 3, placed 3`, the same as `dbt_dev`'s `silver` on Postgres; the job billed 20,971,520 bytes under a 1 GiB cap.
  `make gcp-cost-check` stayed at $0.000010 (the Artifact Registry egress SKU already there; export until 14:35Z), and `make gcp-usage-check` read BigQuery queries at 172.73 GiB before and 172.76 GiB after, of 1 TiB.
  `make bigquery-check` passed with no governed-model drift; with `gov_returns_daily.sql` unquoted by hand it failed (`a reserved word as an unquoted name … 'AS order'`).
  `make lint` passed, and `make agent-test` passed: 439 passed, 1 skipped (the metadata DB was not up).
- Decisions: none; semantic/PLAN.md § 6 now says where to quote.
- Open: a warehouse refusal reaches the model only as "Database Error" (#384).
