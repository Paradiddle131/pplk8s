## 2026-11-03 — Semantic track — row policies through views, table functions and authorized routines, offline (#345)

- Done: `docs/research/semantic-bet/probes/332_bet_rls.sql` (six synthetic orders, one policy for the caller, a view, a table function, an authorized table function, four counts), `332_emulator_check.sh`, the live runner `332_rls_check.sh` (not run: #338), the finding `docs/research/semantic-bet/findings/2026-11-03-345-rls-offline.md`, the register's Q7 row.
- Evidence: the docs (read 2026-11-03) guarantee the row filter through views only and say conversation logging "doesn't look through views"; the lab's BigQuery emulator refuses `CREATE ROW ACCESS POLICY` (`Statement not supported: CreateRowAccessPolicyStatement`), so every path read all 6 rows there.
- Open: the four live counts and the conversation log stay #332's, after #338.
