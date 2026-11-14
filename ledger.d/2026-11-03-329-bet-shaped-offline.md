## 2026-11-03 — Semantic track — the shaped arm's table functions, offline (#329, first part)

- Done: `docs/research/semantic-bet/probes/329_shaped_sql.py` (MetricFlow's compiled BigQuery SQL per saved query, with a date range), `probes/329_bet_shaped.sql` (seven `bet_shaped` table functions written from it), `probes/329_emulator_check.sh`; the finding `docs/research/semantic-bet/findings/2026-11-03-329-bet-shaped.md`; Q4 is `measuring`; #339 filed (the compile-only target's connection test reaches BigQuery through the cloud proxy).
- Evidence: all seven functions created on the BigQuery emulator 0.8.1 and returned the hand-checked answers over 16 fixture rows; MetricFlow filters the date range in every input (three places in `channel_performance`) and moved a start before the time spine to 2000-01-01 without a warning.
- Open: the live part after #338 (dry run, `bet_shaped` on the lab project, `bqRoutines` with a table function, what the data agent uses).
