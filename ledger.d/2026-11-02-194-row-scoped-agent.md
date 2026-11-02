## 2026-11-02 — Semantic track — an agent scoped to Germany's rows (#194)

- Done: Postgres row policies on `silver.customers`, `silver.orders` and `silver.returns` (`dbt/macros/agent_row_scope.sql`, a post-hook on each model and applied by `agent_warehouse` to existing tables) limit the new `agent_metrics_de` role to Germany's customers and their orders and returns; `ops.agent_scopes` holds each role's countries, read through `ops.agent_countries(role)`.
- Done: `semantic_agent.scope` gives every answer from a scoped role a scope statement (`Scoped:`, `Not scoped:` or `Scope unknown:`), which the instruction quotes and `ops.agent_queries.scope` records; images dbt 0.7.42 and semantic-agent 0.1.40.
- Evidence: `agent-standalone-check.sh` as `agent_metrics_de`: revenue by country only DE, 410.75 equal to SQL by hand as the owner, no figure for NL, two audit rows with the scope; `agent-fixture.sh`: the macro applied the three policies to tables built before it.
- Decisions: SL-21 in `semantic/PLAN.md`; the BigQuery mapping in `docs/semantic-layer-on-bigquery.md` (Rows an agent may read).
- Open: `customer_actions` and the other customer-keyed tables are not scoped; the scope lookup on BigQuery is not built.
