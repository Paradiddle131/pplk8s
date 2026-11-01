## 2026-11-01 — Semantic — SourceFreshnessNotChecked fires when no freshness verdict was ever recorded (#225)

- Done: a second `SourceFreshnessNotChecked` rule, `absent(ops_source_freshness_checked_timestamp_seconds)` while the warehouse `sql_exporter` is scraped, held 2 h so a fresh lab stays quiet until its first hourly run; promtool cases for a check that never succeeded (quiet at 90 m, firing at 121 m) and for the exporter down (quiet, `AirflowReadinessMetricsMissing` speaks); runbook § 13.
- Fixed after local verify: promtool linted the two same-named rules as duplicates (`FAILED: lint error 1 duplicate rule(s)`) while `make rules-test` exited 0; the never-recorded rule now carries `reason: never-recorded`, and `rules-test.sh` runs `promtool check rules --lint-fatal`, which fails (exit 2) on the old rule file.
- Evidence: see the PR for the gate counts.
- Decisions: none.
- Open: none.
