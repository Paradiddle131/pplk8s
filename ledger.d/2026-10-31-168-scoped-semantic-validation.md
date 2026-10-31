## 2026-10-31 — Semantic track — finance's semantic gate queries only the domains it waited for; the agent checks fail fast on a refused key

- Done: `finance_daily`'s `validate_semantic_layer` no longer fails on a warehouse where `marketing_elt` has never run (#168): `dbt/scripts/validate_semantic.py` runs MetricFlow's own validators, the whole semantic manifest offline and on the warehouse only the semantic models of the pipelines the DAG waited for (`--pipelines returns,sales`) and the metrics that read only them; a broken returns metric still fails it. `make agent-deploy-check` and `make agent-eval` share one OpenRouter `/key` preflight (`tests/e2e/openrouter-key-check.sh`, `make agent-key-check`), which the deploy check runs before the image builds, so an unset or refused key fails in seconds (#158). dbt 0.7.16, airflow 3.3.1-pplk8s.17.
- Evidence: see the PR.
- Decisions: SL-1 (the stage check in a DAG is scoped to the waited-for pipelines).
- Open: none.
