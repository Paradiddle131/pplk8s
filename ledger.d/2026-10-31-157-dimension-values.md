## 2026-10-31 — Semantic track — the agent sees a categorical dimension's values and refuses a guessed one

- Done: `dbt/scripts/build_catalog.py` carries the values a categorical dimension's column declares (its `accepted_values` test) into `agent.json` as the dimension's `values`; `slv_returns.reason` declares the fixture's codes (`damaged`, `wrong size`, `late delivery`); `describe_metric` shows them, and `query_metrics` refuses a filter value outside them with an error naming them, before MetricFlow runs. A dimension that declares no values (currency, campaign name) passes any value as before. `phase5-check.sh` and `metadata-restore-drill.sh` upload `damaged` instead of made-up reasons the new test would refuse. dbt 0.7.12, semantic-agent 0.1.11.
- Evidence: see the PR.
- Decisions: SL-2 now checks a filter value against the declared values, declared rather than queried so the catalog stays offline; a lesson in semantic/PLAN.md § 6.
- Open: none.
