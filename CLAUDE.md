# pplk8s

A local, single-machine learning lab for running Apache Airflow on Kubernetes.
It rehearses a real GCP data platform's move from Cloud Workflows to Airflow: first self-managed Airflow on GKE, later Cloud Composer.
The work platform is never touched from here; this repo only mimics it.

## The platform being mimicked

Triggers start pipelines; an orchestrator calls an extraction service (EL Factory, a Flask app on Cloud Run) that stages files in GCS and loads BigQuery; then a dbt job (a Cloud Run Job) builds Bronze → Silver → Gold → Exposed layers.
Durable readiness/watermark tables in the warehouse gate cross-pipeline hand-offs.

## Principles

- **Airflow orchestrates; it never processes.** Extraction lives in EL Factory, transformation lives in dbt. DAGs call them and pass only identifiers and compact status.
- **Every GCP service gets a local _stand-in_.** Stand-ins that represent managed services (warehouse, object storage, Pub/Sub, Airflow's metadata DB) run outside the Kubernetes cluster, because their production counterparts sit outside GKE.
- **DAGs stay portable to Cloud Composer.** Business DAGs reach workloads only through a thin seam of shared hooks/helpers; swapping a local stand-in for the real GCP operator is a change inside the seam, never inside a DAG.
- **Keep the target's version line.** Airflow, provider, and Kubernetes versions follow what Cloud Composer and GKE actually offer; [`PLAN.md`](PLAN.md) records the pins and why.
- **Clean-room only.** Rebuild interfaces from their described behaviour, using public or synthetic data; employer code, data, and credentials never enter this repo.
- **Simplest thing that teaches the target.** Add a tool only when a phase's learning goal needs it.

## Two tracks

- **The Airflow lab** (everything below, [`PLAN.md`](PLAN.md), [`LESSONS.md`](LESSONS.md), the `lesson` label): sealed for any other topic; new work there is Phase 8, maintenance, and a pipeline the use case adds for a new domain (D38), built on the existing ELT pattern.
- **The semantic layer and metrics agent** ([`semantic/PLAN.md`](semantic/PLAN.md)): a dbt semantic layer over the same warehouse and an ADK agent that answers through metrics; it shares `dbt/` and the Compose stand-ins, touches a DAG only to give a new domain its lineage (D38), and keeps its decisions, progress rules and lessons in its plan.
  Label its issues `semantic`, never `lesson`.

## Working files

- [`PLAN.md`](PLAN.md): the roadmap, architecture decisions, and phase exit criteria. Read it before starting work; change a decision there, with its rationale, before acting on the change.
- [`LEDGER.md`](LEDGER.md): an append-only log of completed work. Every working session that changed the repo adds one entry, as a fragment `ledger.d/YYYY-MM-DD-<issue-or-pr>-<slug>.md` in the PR that carries the work ([`ledger.d/README.md`](ledger.d/README.md)); `make ledger` on `main` folds merged fragments into `LEDGER.md`. Never edit `LEDGER.md` in a PR, so parallel PRs don't conflict on it.
- [`LESSONS.md`](LESSONS.md): one-line lessons for the real GKE and Composer build (Stages 2-3). Append any lesson a session teaches that applies there; leave out anything that only matters on the local machine.
- Lessons go by track: the Airflow lab's to `LESSONS.md`; the semantic track's, the GCP lab project under `platform/gcp/` included (BigQuery, Cloud Run, IAM, quotas, Monitoring, Artifact Registry, billing), to [`semantic/PLAN.md`](semantic/PLAN.md) § 6.
  Before closing a session that changed the repo, ask what it taught the work platform, and write each answer as one line with its evidence.
- [`docs/agents/autopilot.md`](docs/agents/autopilot.md): the profile for unattended cloud wakes (the `autopilot` skill in loadout plus this repo's slots); loadout provisions cloud sessions (`cloud/setup.sh pplk8s`), so this repo keeps no setup script of its own.
- GitHub label `lesson`: put it on every issue or PR whose work likely teaches a LESSONS.md lesson for GKE (Stage 2) or Composer (Stage 3); leave lab-only problems (WSL2, kind, local stand-ins, this repo's own CI) unlabelled. `gh issue list -l lesson` is the queue of what to tackle next for the lessons.

## Conventions

- Put each sentence of Markdown prose on its own line.
- Every component comes up and down through a single scripted entry point; a fresh clone plus documented prerequisites reproduces the lab.
- The GCP lab project bills $0.00: every live step follows [`platform/gcp/README.md`](platform/gcp/README.md)'s $0.00 rule (free-path services only, `make gcp-cost-check` before and after, never a raised quota, cap or budget, with one exception: the owner's own raise of BigQuery's daily query fence to 0.2 TiB, a per-day brake under the month's free 1 TiB (owner, 2026-11-03, [#370](../../issues/370)), which an agent records and never changes); incidental charges under $1.00 a month pass the cost check and are listed (owner, 2026-11-03).
- Work counts as done when its check passes: the phase's exit criterion, a test, or an observed run.
- Name the GitHub owner and repo through the origin remote (Makefile `GITHUB_REPO`), and link this repo's issues relatively (`../../issues/N`), so a fork works against itself; on cloud, loadout's pre-commit guard (`cloud/githooks/check-portable.sh`) refuses a commit that adds the owner's login. History (`LEDGER.md`, `ledger.d/`, dated decisions) keeps its facts.
