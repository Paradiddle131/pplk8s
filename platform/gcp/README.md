# platform/gcp — the semantic track on a real GCP project, at $0.00

Everything that only a real GCP project uses lives here (`semantic/PLAN.md` SL-13).
Code that runs in both worlds stays in its component behind its seam (a dbt output, the agent's toolset, session and model seams, dispatch macros); the local stand-ins never move here.
The project is held to the Always Free tier: one cent of spend stops the work, and the guard rails below come before any live step.

| Path | What it is | Stand-in it replaces | Status |
|---|---|---|---|
| `free-path.yaml` | every API and OpenTofu resource type the project may use, each with its free-tier source; the APIs GCP turns on by itself; the caps; the paid list | — | in `make gcp-validate` |
| `check_free_path.py`, `tests/` | fails on anything off the free path, offline | — | in `make gcp-validate` |
| `check_gcp_builds.py` | SL-19's check: each GCP image build's lockfile holds no Postgres package and its stage copies no TLC path, offline | — | in `make gcp-validate` |
| (`dbt/Dockerfile`, `WAREHOUSE=bigquery`) | `make gcp-images`: the dbt image for GCP (149 MiB stored, #206) built and pushed to `<region>-docker.pkg.dev/<project>/pplk8s/dbt:<DBT_IMAGE's version>`; `make gcp-image-check` runs it on the emulator first | the local `dbt` image in the kind registry | waits for `gcp-up`'s repository |
| `infra/` | the one OpenTofu root: the free-path APIs, the kill switch, Artifact Registry's `pplk8s` Docker repository (two versions per image, scanning off; #230), the BigQuery datasets, workload service accounts and their grants, the daily query quota, Firestore's free database (#205) | Compose and kind; the kind registry (`localhost:5001`) | applied by the owner; #230's and #205's resources wait for `gcp-up` |
| `access.yaml` | each workload's service account and the datasets it reads or writes, held to the lab's roles by `tests/test_access.py` | the warehouse roles of `dbt/macros/agent_warehouse.sql` | in `make gcp-validate` |
| `guardrails-check.sh` | `make gcp-guardrails-check`: reads back the daily query quota, the enabled APIs against the free path, Firestore's databases and the byte cap (#205) | — | live: ok |
| `tofu.sh` | `make gcp-plan`, `gcp-up`, `gcp-down`: credentials, the state at `gs://<project>-tfstate/default.tfstate` (no slash in the name: the cloud proxy breaks slashed object names), refuses without `GCP_PROJECT` | — | applied; `gcp-plan`: no changes |
| `cost-check.sh` | `make gcp-cost-check`: the month's cost from the billing export, by service and SKU (#233) | — | live: no export rows yet |
| (dbt's `gcp` output, `tests/e2e/bigquery-run-check.sh`) | `make bigquery-live-check`: the emulator check on the lab project: its dbt datasets emptied, the fixture loaded by load jobs, the semantic path built and its metrics asserted against gold, then the bytes billed; the cost check before and after (#206) | `make bigquery-emulator-check` | live: passed 2026-11-01, 7.8 GiB billed, $0.00 |

## The $0.00 rule

- Use only what `free-path.yaml` lists; a new API or resource type joins it, with its source, in the PR that needs it, and `make gcp-validate` (in `make lint`) refuses anything else.
- Run `make gcp-cost-check` before and after every live step; exit 1 (a cost) or 3 (not provable yet) means no live GCP work until the owner says so.
- Dry-run a query before running it, and keep `maximum_bytes_billed` on every job; no streaming inserts (no free tier).
- Artifact Registry holds at most 0.5 GiB-month across the billing account: images go there only to be pulled by Cloud Run in us-central1, never pulled to a laptop or a cloud session (internet egress), and the Container Scanning and On-Demand Scanning APIs stay off (billed per image).
- Never raise a quota, a cap or the budget, and never test a permission by attempting the action: ask with `testIamPermissions`.
- Cloud sessions also carry claude-dotfiles' GCP kit (its `cloud/gcp/README.md`): a guard in front of every Bash command and a session-start line with the month-to-date cost.

## Identities

| Who | Roles on the project | Does |
|---|---|---|
| The owner, from their own signed-in shell | Owner | `make gcp-up` / `gcp-down`, enabling APIs, IAM, quotas, the budget |
| `pplk8s-automation`, the cloud sessions' credential (injected by the egress proxy, no key) | Viewer, BigQuery Job User and Data Editor, Service Usage Consumer; Storage Object Viewer on the state bucket; Artifact Registry Writer on the `pplk8s` repository (`infra/`) | reads, `make gcp-plan`, `make gcp-cost-check`, BigQuery work, pushing the lab's images |
| `dbt-runner`, `semantic-agent`, `agent-audit` (created by `infra/` from `access.yaml`) | BigQuery Job User; Data Editor on dbt's datasets and Data Viewer on `ds_source` (dbt), Data Viewer on `silver` and `semantic` (the agent), none yet (the audit writer, whose insert-only grant on `ops.agent_queries` comes with the table, #209) | run the dbt build, the agent's queries, the audit inserts (from #206 and #209) |
| `kill-switch` (created by `infra/`) | Project Billing Manager, Workflows Invoker, Eventarc Event Receiver, Logs Writer | unlinks billing when the budget passes `kill_switch_usd` |

The cloud sessions' credential holds no role that can enable an API, change IAM or quotas, or buy capacity, so a mistake there cannot spend; a product's role is added by the owner when an issue reaches it.

## Guard rails in place

- BigQuery query usage per day and per user: 31,457 MiB (`free-path.yaml` `caps`; set by hand in #226, imported and held by `infra/bigquery.tf`): 31 days of it stay under the free 1 TiB, and `make gcp-validate` fails a higher cap.
- Firestore: only the `(default)` database, which is the free one, with point-in-time recovery off; no TTL policies or backups (billed from the first byte).
- `make gcp-guardrails-check` reads these back from the project, and fails on any enabled API that is not on the free path.
- `~/.bigqueryrc` in cloud sessions: 1 GiB `maximum_bytes_billed` per query; dbt's `gcp` output and the live check's client cap every job at the same `caps.bigquery_maximum_bytes_billed` (held by `tests/test_dbt_gcp_output.py`).
- A 1 USD budget on the billing account, alerting by email; the billing export to `billing_export` (US).
- Off: BigQuery Reservation, Dataplex, Cloud SQL and the "Google Cloud APIs" bundle that kept them on.

## The kill switch

The cents are for alerts and for stopping sessions; the kill switch is for a runaway the other rails missed.
The budget publishes to `budget-alerts` several times a day; Eventarc hands each message to the `kill-switch` workflow, which unlinks billing once the month-to-date cost after credits passes `kill_switch_usd` (default 5 USD, at most 20).
Unlinking billing stops every resource and may delete some, which for a lab of synthetic data is the right trade.
It costs nothing: Pub/Sub's first 10 GiB a month, Eventarc's Pub/Sub-sourced events ($0) and Workflows' 5,000 free internal steps a month, at one step per notification; nothing is built or stored.
Billing data lags by hours, so it limits a runaway rather than preventing one; Workflows' free steps are shared with the orchestration of #228, which must count them.

## Owner's runbook (a shell signed in to gcloud: WSL or Cloud Shell)

1. Once: the state bucket, readable by the cloud sessions' credential.

```bash
P=<project id>
gcloud storage buckets create "gs://$P-tfstate" --project="$P" --location=us-central1 --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets add-iam-policy-binding "gs://$P-tfstate" --member="serviceAccount:pplk8s-automation@$P.iam.gserviceaccount.com" --role=roles/storage.objectViewer
```

2. Apply: `export GCP_PROJECT=$P` (in `~/.bashrc` on a laptop: the `gcp-` targets refuse without it, so they never act on gcloud's active project by accident), `make tools` (OpenTofu into `~/.local/bin`), then `GCP_PROJECT=$P make gcp-up`; `tofu.sh` borrows a short-lived token from the active gcloud account (it prints which; `GCP_ACCOUNT=<account>` picks another), so no `gcloud auth application-default login` is needed; `make bigquery-live-check` borrows its token the same way (#275).
3. Connect the budget to the kill switch (console): Billing → Budgets & alerts → the lab's budget → Manage notifications → Connect a Pub/Sub topic → the project's `budget-alerts` → Save.
4. Check: `GCP_PROJECT=$P make gcp-plan` from a cloud session shows no changes; the workflow's executions (Workflows → `kill-switch`) end after one step.

When the lab ends: `make gcp-down`, then delete the project.
