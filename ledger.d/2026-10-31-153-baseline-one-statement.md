## 2026-10-31 — Semantic — The baseline's SQL runs as one statement, so its read-only transaction and timeout hold (#153)

- Done: `execute_sql` in `services/semantic-agent/src/sql_baseline/agent.py` sends the model's SQL with `prepare=True`, so psycopg uses the extended query protocol and Postgres refuses a string of several statements (`cannot insert multiple commands into a prepared statement`) before any of them runs. Before, `commit; begin read write; …` left the read-only transaction and `commit; set statement_timeout = 0; select pg_sleep(11)` ran 11 s past the 10 s timeout. `tests/test_services.py` covers both strings and a `%` in the SQL. semantic-agent 0.1.10.
- Evidence: see the PR.
- Decisions: none; SL-10's rationale now says the read-only transaction could be left, and a lesson in semantic/PLAN.md § 6.
- Open: none.
