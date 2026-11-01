## 2026-11-01 — Semantic — The lab's images fit Artifact Registry's free tier, and only what a GCP deployment runs ships to GCP (#230)

- Done: `platform/gcp/infra/artifact_registry.tf` declares the `pplk8s` Docker repository in us-central1 (immutable tags, a cleanup policy keeping each image's two newest versions, vulnerability scanning disabled) and Artifact Registry Writer on it for the cloud sessions' credential; `free-path.yaml` enables `artifactregistry.googleapis.com`, lists its two resource types, and puts the Container Scanning and On-Demand Scanning APIs on the paid list; the runbook says images are pulled only by Cloud Run in us-central1.
- Done: the semantic agent's image installs `google-adk[db]` and `litellm` instead of ADK's `eval` and `extensions` extras (62 packages fewer), and leaves out the eval module and dbt's singular tests; uv groups `dev` (test and lint tools) and `eval` (the agent eval) are never installed in an image; `AGENT_IMAGE` 0.1.26.
- Done: `semantic/PLAN.md` SL-19, what ships to GCP: a per-warehouse build of each image (`WAREHOUSE=bigquery`), no Postgres, TLC, tests, fixtures or eval code, a check in `make gcp-validate` with the first GCP image; dbt's GCP target is named `gcp`; #206, #209 and #227 carry it as acceptance.
- Evidence: see the PR for `make gcp-validate`, the live `make gcp-plan`, the agent checks and the measured image sizes before and after.
- Decisions: SL-19 (owner, 2026-11-01).
- Open: the owner's `make gcp-up`; TLC out of the dbt image's GCP build (#206 decides how).
