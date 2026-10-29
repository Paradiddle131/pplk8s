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

- **The Airflow lab** (everything below, [`PLAN.md`](PLAN.md), [`LESSONS.md`](LESSONS.md), the `lesson` label): sealed for any other topic; new work there is Phase 8 and maintenance.
- **The semantic layer and metrics agent** ([`semantic/PLAN.md`](semantic/PLAN.md)): a dbt semantic layer over the same warehouse and an ADK agent that answers through metrics; it shares `dbt/` and the Compose stand-ins, never touches a DAG, and keeps its decisions, progress rules and lessons in its plan.
  Label its issues `semantic`, never `lesson`.

## Working files

- [`PLAN.md`](PLAN.md): the roadmap, architecture decisions, and phase exit criteria. Read it before starting work; change a decision there, with its rationale, before acting on the change.
- [`LEDGER.md`](LEDGER.md): an append-only log of completed work. Every working session that changed the repo adds one entry, as a fragment `ledger.d/YYYY-MM-DD-<issue-or-pr>-<slug>.md` in the PR that carries the work ([`ledger.d/README.md`](ledger.d/README.md)); `make ledger` on `main` folds merged fragments into `LEDGER.md`. Never edit `LEDGER.md` in a PR, so parallel PRs don't conflict on it.
- [`LESSONS.md`](LESSONS.md): one-line lessons for the real GKE and Composer build (Stages 2-3). Append any lesson a session teaches that applies there; leave out anything that only matters on the local machine.
- [`docs/agents/autopilot.md`](docs/agents/autopilot.md): the profile for unattended cloud wakes (the `autopilot` skill in claude-dotfiles plus this repo's slots); its setup script is `docs/agents/cloud-setup.sh`.
- GitHub label `lesson`: put it on every issue or PR whose work likely teaches a LESSONS.md lesson for GKE (Stage 2) or Composer (Stage 3); leave lab-only problems (WSL2, kind, local stand-ins, this repo's own CI) unlabelled. `gh issue list -l lesson` is the queue of what to tackle next for the lessons.

## Conventions

- Put each sentence of Markdown prose on its own line.
- Every component comes up and down through a single scripted entry point; a fresh clone plus documented prerequisites reproduces the lab.
- Work counts as done when its check passes: the phase's exit criterion, a test, or an observed run.
