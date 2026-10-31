## 2026-10-31 — Semantic — Side-by-side migration rehearsal with a parity report per consumer (#133)

- Done: three tables built the old way in a `legacy` dataset (`lgc_daily_net_sales`, `lgc_country_sales`, whose revenue counts cancelled orders, `lgc_channel_daily`); the consumers as dbt exposures (a finance dashboard, a sales agent, a marketing automation) naming what each reads; `migration.parity` comparing each consumer's old table with its new model per field through `hop_mismatches`; the gate `consumers_switch_on_parity`; `make migration-check`; the written plan in `docs/migration-rehearsal.md`. The dashboard is switched; the agent waits on its revenue difference, the automation on the agent. dbt 0.7.11, semantic-agent 0.1.9.
- Evidence: see the PR.
- Decisions: SL-11 added: migrations are rehearsed with consumers as exposures and a parity gate in `dbt build`.
- Open: none.
