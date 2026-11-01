## 2026-11-01 — Semantic — Catch label drift: a new model version and shifting label shares in the call signals (#248)

- Done: the dbt test `call_label_model_versions_scored` (labels of the current prompt version from a model version the golden set was not labelled by fail the build); `slv_call_label_shares` (alias `silver.call_label_shares`), each signal's label shares per ISO week with a p-chart band from the trailing weeks (`call_label_drift` in `dbt_project.yml`, a dbt unit test for its arithmetic, the `iso_week_start` dialect seam); the warehouse `sql_exporter` collector `call_label_shares`; the `CallLabelShareDrift` rule with promtool tests; runbook § 14; SL-18 and `docs/text-signals.md`; dbt image 0.7.23.
- Evidence: see the PR for the gate counts; the unit test caught Postgres' `greatest`/`least` skipping a NULL, which had given bandless weeks a [0, 1] band.
- Decisions: semantic/PLAN.md SL-18 (extended).
- Open: the fixture's calls fill one week, so the lab's own data never has a band; a multi-week fixture would show the alert end to end.
