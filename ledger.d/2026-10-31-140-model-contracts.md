## 2026-10-31 — Semantic — Model contracts on every model agents read (#140)

- Done: gold and exposed enforce dbt model contracts (`+contract: {enforced: true}` per layer), and every one of their columns declares a `data_type` spelled for Postgres and BigQuery alike (strings through a `text` YAML anchor). `check_standard.py` fails a public model without an enforced contract or a column without a type; `make semantic-check` shows `dbt build` failing on a renamed and a retyped public column with dbt's contract error. The agent-ready standard, the dbt README and `docs/semantic-layer-on-bigquery.md` name contracts as the public-model rule. dbt image 0.7.8, semantic-agent 0.1.5.
- Evidence: see the PR.
- Decisions: SL-4 amended: public models enforce a typed contract.
- Open: none.
