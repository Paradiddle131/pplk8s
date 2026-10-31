# platform/gcp — the semantic track on a real GCP project, at $0.00

Everything that only a real GCP project uses lives here (`semantic/PLAN.md` SL-13).
Code that runs in both worlds stays in its component behind its seam (a dbt output, the agent's toolset, session and model seams, dispatch macros); the local stand-ins never move here.
The project is held to the Always Free tier: one cent of spend stops the work, and the guard rails below come before any live step.

| Path | What it is | Stand-in it replaces | Status |
|---|---|---|---|
| `free-path.yaml` | every API and OpenTofu resource type the project may use, each with its free-tier source; the paid list | — | in `make gcp-validate` |
| `check_free_path.py`, `tests/` | fails on anything off the free path, offline | — | in `make gcp-validate` |
| `infra/` | the one OpenTofu root: the free-path APIs and the kill switch | Compose and kind | prepared, never applied |
| `tofu.sh` | `make gcp-plan`, `gcp-up`, `gcp-down`: credentials, state bucket, refuses without `GCP_PROJECT` | — | |
| `cost-check.sh` | `make gcp-cost-check`: the month's cost from the billing export, by service and SKU (#233) | — | live: no export rows yet |

## The $0.00 rule

- Use only what `free-path.yaml` lists; a new API or resource type joins it, with its source, in the PR that needs it, and `make gcp-validate` (in `make lint`) refuses anything else.
- Run `make gcp-cost-check` before and after every live step; exit 1 (a cost) or 3 (not provable yet) means no live GCP work until the owner says so.
- Dry-run a query before running it, and keep `maximum_bytes_billed` on every job; no streaming inserts (no free tier).
- Never raise a quota, a cap or the budget, and never test a permission by attempting the action: ask with `testIamPermissions`.
- Cloud sessions also carry claude-dotfiles' GCP kit (its `cloud/gcp/README.md`): a guard in front of every Bash command and a session-start line with the month-to-date cost.

## Identities

| Who | Roles on the project | Does |
|---|---|---|
| The owner, from Cloud Shell | Owner | `make gcp-up` / `gcp-down`, enabling APIs, IAM, quotas, the budget |
| `pplk8s-automation`, the cloud sessions' credential (injected by the egress proxy, no key) | Viewer, BigQuery Job User and Data Editor, Service Usage Consumer; Storage Object Viewer on the state bucket | reads, `make gcp-plan`, `make gcp-cost-check`, BigQuery work |
| `kill-switch` (created by `infra/`) | Project Billing Manager, Workflows Invoker, Eventarc Event Receiver, Logs Writer | unlinks billing when the budget passes `kill_switch_usd` |

The cloud sessions' credential holds no role that can enable an API, change IAM or quotas, or buy capacity, so a mistake there cannot spend; a product's role is added by the owner when an issue reaches it.

## Guard rails in place

- BigQuery query usage per day and per user: 31,457 MiB (set by hand, #226; #205 codifies it).
- `~/.bigqueryrc` in cloud sessions: 1 GiB `maximum_bytes_billed` per query.
- A 1 USD budget on the billing account, alerting by email; the billing export to `billing_export` (US).
- Off: BigQuery Reservation, Dataplex, Cloud SQL and the "Google Cloud APIs" bundle that kept them on.

## The kill switch

The cents are for alerts and for stopping sessions; the kill switch is for a runaway the other rails missed.
The budget publishes to `budget-alerts` several times a day; Eventarc hands each message to the `kill-switch` workflow, which unlinks billing once the month-to-date cost after credits passes `kill_switch_usd` (default 5 USD, at most 20).
Unlinking billing stops every resource and may delete some, which for a lab of synthetic data is the right trade.
It costs nothing: Pub/Sub's first 10 GiB a month, Eventarc's Pub/Sub-sourced events ($0) and Workflows' 5,000 free internal steps a month, at one step per notification; nothing is built or stored.
Billing data lags by hours, so it limits a runaway rather than preventing one; Workflows' free steps are shared with the orchestration of #228, which must count them.

## Owner's runbook (Cloud Shell)

1. Once: the state bucket, readable by the cloud sessions' credential.

```bash
P=<project id>
gcloud storage buckets create "gs://$P-tfstate" --project="$P" --location=us-central1 --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets add-iam-policy-binding "gs://$P-tfstate" --member="serviceAccount:pplk8s-automation@$P.iam.gserviceaccount.com" --role=roles/storage.objectViewer
```

2. Apply: `git clone` this repo, `make tools` (OpenTofu into `~/.local/bin`), then `GCP_PROJECT=$P make gcp-up`.
3. Connect the budget to the kill switch (console): Billing → Budgets & alerts → the lab's budget → Manage notifications → Connect a Pub/Sub topic → the project's `budget-alerts` → Save.
4. Check: `GCP_PROJECT=$P make gcp-plan` from a cloud session shows no changes; the workflow's executions (Workflows → `kill-switch`) end after one step.

When the lab ends: `make gcp-down`, then delete the project.
