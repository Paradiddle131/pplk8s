## 2026-10-31 — Semantic — The agent-ready warehouse standard and its check (#128)

- Done: `docs/agent-ready-warehouse.md` states the standard agents rely on: a dataset and model prefix per layer, the relation named without the prefix, snake case, which models are public, where each calculated field lives, what every model, column and metric description says, and how the words reach BigQuery descriptions, Knowledge Catalog and a data agent. `dbt/scripts/check_standard.py` replaces `check_metrics.py` and enforces it offline on every parse, in `make dbt-validate` and the dbt image build; `semantic-check.sh` shows an unprefixed, undescribed gold model and an undescribed metric failing it. dbt image 0.7.6 and semantic-agent 0.1.3 (both carry the dbt project).
- Evidence: see the PR.
- Decisions: SL-4 amended: the standard and its check; `dbt-project-evaluator` rejected for it.
- Open: none.
