## 2026-11-01 — Semantic — Artifact Registry on the free path: one repository, two versions per image, scanning off (#230, first step)

- Done: `platform/gcp/infra/artifact_registry.tf` declares the `pplk8s` Docker repository in us-central1 (immutable tags, a cleanup policy keeping each image's two newest versions, vulnerability scanning disabled) and Artifact Registry Writer on it for the cloud sessions' credential; `free-path.yaml` enables `artifactregistry.googleapis.com`, lists its two resource types, and puts the Container Scanning and On-Demand Scanning APIs on the paid list; the runbook says images are pulled only by Cloud Run in us-central1.
- Evidence: see the PR for `make gcp-validate`, the live `make gcp-plan` (3 to add, 0 to change or destroy) and the measured image sizes.
- Decisions: none; the images are not slimmed here, so the open PRs' tag bumps (D16) are untouched.
- Open: the owner's `make gcp-up`; slimming the images under 0.45 GiB (#230's second step, after the open semantic PRs land).
