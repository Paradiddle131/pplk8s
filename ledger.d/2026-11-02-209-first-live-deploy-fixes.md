## 2026-11-02 — Semantic — Three fixes from the first live `gcp-workloads-up` on the lab project (#209)

- Done: `infra/monitoring.tf`: the freshness alert's condition holds `duration = "60s"`, not `0s`, and `infra/tests/monitoring.tftest.hcl` asserts a non-zero duration.
  `dbt/macros/agent_warehouse.sql` creates a schema only when `adapter.check_schema_exists` finds it missing.
  `guardrails-check.sh` writes each Cloud Run service's IAM policy as one compact JSON line.
- Why: the owner's deploy, run locally on 2026-11-02, failed three times.
  Cloud Monitoring refused the alert policy: "evaluation_missing_data ... must have a non-zero duration".
  The `run-operation agent_warehouse` Job failed with "User does not have bigquery.datasets.create permission": dbt-bigquery's `create_schema` calls `datasets.insert`, which BigQuery authorises before it finds the dataset exists, and the dbt Job's service account rightly holds no such grant (infra/ creates every dataset).
  `gcp-guardrails-check` crashed with a `JSONDecodeError` once a service existed: the API pretty-prints its policy over many lines, and the reader split it per line.
- Evidence: from this branch, `gcp-workloads-up`'s steps without the cost check (UNKNOWN: no billing export rows yet) ran through: both images pushed (339 MB stored, under the free 0.5 GiB), both applies, `run-operation agent_warehouse` (exit 0; `ops.agent_queries`, `ops.readiness`, `ops.product_deadlines`) and `dbt build` (PASS=173, ERROR=0); `make gcp-guardrails-check` ok on every line, including the agent service (0 to 1 instances, invoker IAM on, none public) and both Jobs; `make gcp-plan` "No changes"; `make agent-warehouse` on the Compose warehouse still passes; `make gcp-validate` passes, and the new `tofu test` assertion fails on `0s`.
  semantic/PLAN.md § 6 gained three lessons (the instance quota, moved from `LESSONS.md` where #309 put it; the dbt Job's dataset check; the alert's duration), and CLAUDE.md and § 5 now route lessons by track: the semantic track's, the GCP lab project included, to § 6.
- Decisions: none changed; semantic/PLAN.md SL-13 (the alert, the Job's least privilege).
- Open: the agent's live answer: its one question got "the model's daily request quota is spent" (OpenRouter's free quota, reset 2026-11-03T00:00Z), so no audit row yet; the Firestore session was written.
