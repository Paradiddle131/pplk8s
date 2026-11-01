## 2026-11-01 — Semantic — The lab project as code: datasets, workload identities, the query quota and Firestore (#205)

- Done: `platform/gcp/access.yaml` and `infra/bigquery.tf` declare the nine datasets dbt builds and reads (US), the `dbt-runner`, `semantic-agent` and `agent-audit` service accounts with BigQuery Job User and the dataset grants of the lab role each stands for (option A); the two BigQuery daily query quotas, imported from the console's preferences by `tofu.sh` and held at `caps.bigquery_query_mib_per_day`; `infra/firestore.tf` the `(default)` Standard database with point-in-time recovery off; `free-path.yaml` turns Firestore on, lists the APIs GCP turns on by itself and the caps; `make gcp-guardrails-check` reads the stops back.
- Evidence: see the PR for `make gcp-validate`, the live `make gcp-plan` and `make gcp-guardrails-check`, and the guardrails check failing on a stray API and a lowered cap.
- Decisions: none new; Cloud Run's spend caps move to #209, where its API is turned on.
- Open: the owner's `make gcp-up`; the table-level grants on `ops` (#209).
