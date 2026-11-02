## 2026-11-02 — Semantic track — personal columns refused to every agent role (#193)

- Done: `dbt/macros/agent_pii_columns.sql`, a post-hook on every model and re-applied by `agent_warehouse`: a column marked `meta: {pii: true}` is readable by the relation's owner and its `config.meta.pii_readers` only; every other role holding the relation keeps SELECT on the other columns, so `select *` fails for `agent_metrics` and `agent_sql`, and the new `outreach_automation` login reads `exposed.outreach_activation` whole.
- Done: `check_standard.py` fails a semantic-stage model with a personal column, a semantic model naming one as a dimension or an entity, and a table's personal column without `policy_tags`; `silver.partner_contacts` carries `policy_tags` from the var `pii_policy_tag`, persisted only when it names a tag; images dbt 0.7.43 and semantic-agent 0.1.41.
- Evidence: `make agent-columns-check` PASS (warehouse first, again, rebuilt), and it fails with the post-hook removed; `make semantic-check` shows the two new standard failures.
- Decisions: SL-22 in `semantic/PLAN.md`; the BigQuery mapping in `docs/semantic-layer-on-bigquery.md` (Personal data by column).
- Open: what a Data Catalog taxonomy costs on the lab project (Unverified in the mapping doc).
