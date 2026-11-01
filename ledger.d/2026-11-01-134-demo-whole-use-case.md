## 2026-11-01 — Semantic — The demo walks the whole use case, on the BigQuery emulator where it runs (#134)

- Done: `docs/demo.md` is rewritten around U1-U6: the layers and cost per booking queried through MetricFlow on the emulator, the standard's check and the column descriptions BigQuery holds, the agent answering with its freshness (live in `make agent-web`, scripted in the check), a stopped source (dbt source freshness, its exporter, SourceStale's promtool tests) and a number changed in gold failing two layer hops on the emulator, the audit trail, and `migration.parity` on the emulator. Each step is `make demo STEP=<step>` (`tests/e2e/demo.sh`, which asserts what it prints); `make demo-check` rehearses them all, timed, with no model quota. `tests/e2e/lib/bigquery_emulator.py` reads the emulator's tables, columns and queries; `make lint` covers it.
- Evidence: see the PR.
- Decisions: none.
- Open: the agent and the freshness exporter still read the Compose Postgres, not the emulator (the doc says why).
