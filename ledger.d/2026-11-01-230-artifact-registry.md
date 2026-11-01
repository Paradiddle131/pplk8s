## 2026-11-01 — Semantic — The lab's images fit Artifact Registry's free tier: one repository, two versions per image, scanning off, a serving-only agent image (#230)

- Done: `platform/gcp/infra/artifact_registry.tf` declares the `pplk8s` Docker repository in us-central1 (immutable tags, a cleanup policy keeping each image's two newest versions, vulnerability scanning disabled) and Artifact Registry Writer on it for the cloud sessions' credential; `free-path.yaml` enables `artifactregistry.googleapis.com`, lists its two resource types, and puts the Container Scanning and On-Demand Scanning APIs on the paid list; the runbook says images are pulled only by Cloud Run in us-central1.
- Done: the semantic agent's image installs `google-adk[db]` and `litellm` instead of ADK's `eval` and `extensions` extras (62 packages fewer); the eval's extra moves to the dev group, which `uv run` installs; `AGENT_IMAGE` 0.1.25.
- Evidence: see the PR for `make gcp-validate`, the live `make gcp-plan`, the agent tests and the measured image sizes before and after.
- Decisions: none.
- Open: the owner's `make gcp-up`.
