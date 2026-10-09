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

## Working files

- [`PLAN.md`](PLAN.md): the roadmap, architecture decisions, and phase exit criteria. Read it before starting work; change a decision there, with its rationale, before acting on the change.
- [`LEDGER.md`](LEDGER.md): an append-only log of completed work. Append an entry at the end of every working session that changed the repo.

## Conventions

- Put each sentence of Markdown prose on its own line.
- Every component comes up and down through a single scripted entry point; a fresh clone plus documented prerequisites reproduces the lab.
- Work counts as done when its check passes: the phase's exit criterion, a test, or an observed run.
