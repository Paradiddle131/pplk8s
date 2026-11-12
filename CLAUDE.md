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
- **Keep the target's version line.** Airflow, provider, and Kubernetes versions follow what Cloud Composer and GKE actually offer; a pin states why beside it (a comment, or its component's README), and [`PLAN.md`](PLAN.md) keeps the reasons of the pins it already holds.
- **Clean-room only.** Rebuild interfaces from their described behaviour, using public or synthetic data; employer code, data, and credentials never enter this repo.
- **Simplest thing that teaches the target.** Add a tool only when a phase's learning goal needs it.

## Two tracks

- **The Airflow lab** (everything below, [`PLAN.md`](PLAN.md), [`LESSONS.md`](LESSONS.md), the `lesson` label): sealed for any other topic; new work there is the monthly TLC file pipeline, maintenance, and a pipeline the use case adds for a new domain, built on the existing ELT pattern like `sales_elt`, so one lineage runs from a DAG run to an agent's answer.
- **The semantic layer and metrics agent** ([`semantic/PLAN.md`](semantic/PLAN.md)): a dbt semantic layer over the same warehouse and an ADK agent that answers through metrics; it shares `dbt/` and the Compose stand-ins, and touches a DAG only to give a new domain that lineage.
  Label its issues `semantic`, never `lesson`.

## Where things are recorded

- **The tracker holds progress, decisions, evidence and lessons.**
  An issue holds the work and the weighing of a choice (options, the owner's call); the PR that closes it is the record of the change, in the `pr` skill's shape: what changed, the check that passed, the choices made, the lessons for work.
  A plan, analysis or visual a session made goes on its issue as an artifact (the `issue` skill).
- **The files describe the system as it is now.**
  A choice with a lasting reason states that reason in present tense, in words, where the design is described: the component's README, `docs/`, or a comment at the code it shapes; no decision row and no id.
- **No process ids in a line you add to a checked-in file:** no issue or PR numbers or links to them, no phase, stage or milestone numbers, no decision ids from the plans' registers; name the work for what it does.
  Commit messages and PR bodies cite issues (`Closes #<n>` in the body).
  On cloud, loadout's pre-commit check (`cloud/githooks/check-process-ids.py`) refuses a commit that adds one; it reads only added lines, so the ids already in the tree stay.
- **Frozen history, read but never appended to:** [`PLAN.md`](PLAN.md) (roadmap, decisions, phase exit criteria), [`semantic/PLAN.md`](semantic/PLAN.md) (the semantic track's goal, requirements, decision register, steps and lessons), [`LESSONS.md`](LESSONS.md), [`LEDGER.md`](LEDGER.md) and [`ledger.d/`](ledger.d/README.md).
  Read them for the reasons behind what exists; where one disagrees with the code or a newer present-tense line, those win.
  No session adds a ledger fragment, a plan row or a lessons line; moving their content onto the tracker is its own follow-up issue.
- **Lessons for the work platform:** before closing a session that changed the repo, ask what it taught the work platform, and write each answer as one line with its evidence under `Lessons for work` in the PR body; a lesson that changes how this repo is built also lands as a present-tense reason or a rule here.
  The Airflow lab's lessons (self-managed Airflow on GKE, then Cloud Composer) go on PRs labelled `lesson`; the semantic track's, the GCP lab project under `platform/gcp/` included (BigQuery, Cloud Run, IAM, quotas, Monitoring, Artifact Registry, billing), on PRs labelled `semantic`.
- GitHub label `lesson`: put it on every issue or PR whose work likely teaches a lesson for the GKE build or for Composer; leave lab-only problems (WSL2, kind, local stand-ins, this repo's own CI) unlabelled.
  `gh issue list -l lesson` is the queue of what to tackle next for the lessons.
- [`docs/agents/autopilot.md`](docs/agents/autopilot.md): the profile for unattended cloud wakes (the `autopilot` skill in loadout plus this repo's slots); loadout provisions cloud sessions (`cloud/setup.sh pplk8s`), so this repo keeps no setup script of its own.

## Conventions

- Put each sentence of Markdown prose on its own line.
- Every component comes up and down through a single scripted entry point; a fresh clone plus documented prerequisites reproduces the lab.
- The GCP lab project bills $0.00: every live step follows [`platform/gcp/README.md`](platform/gcp/README.md)'s $0.00 rule (free-path services only, `make gcp-cost-check` before and after, never a raised quota, cap or budget, with one exception: the owner's own raise of BigQuery's daily query fence to 0.2 TiB, a per-day brake under the month's free 1 TiB (owner, 2026-11-03, [#370](../../issues/370)), which an agent records and never changes); incidental charges under $1.00 a month pass the cost check and are listed (owner, 2026-11-03).
- Work counts as done when its check passes: the phase's exit criterion, a test, or an observed run.
- Name the GitHub owner and repo through the origin remote (Makefile `GITHUB_REPO`), so a fork works against itself; on cloud, loadout's pre-commit guard (`cloud/githooks/check-portable.sh`) refuses a commit that adds the owner's login. History (the frozen files above, dated owner quotes) keeps its facts.
