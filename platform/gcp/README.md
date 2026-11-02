# platform/gcp — the semantic track on a real GCP project, at $0.00

Everything that only a real GCP project uses lives here (`semantic/PLAN.md` SL-13).
Code that runs in both worlds stays in its component behind its seam (a dbt output, the agent's toolset, session and model seams, dispatch macros); the local stand-ins never move here.
The project is held to the Always Free tier: one cent of spend stops the work, and the guard rails below come before any live step.

| Path | What it is | Stand-in it replaces | Status |
|---|---|---|---|
| `free-path.yaml` | every API and OpenTofu resource type the project may use, each with its free-tier source; the APIs GCP turns on by itself; the caps; the paid list | — | in `make gcp-validate` |
| `check_free_path.py`, `tests/` | fails on anything off the free path, offline | — | in `make gcp-validate` |
| `check_gcp_builds.py` | SL-19's check: each GCP image build's lockfile holds no Postgres package and its stage copies no TLC path, offline | — | in `make gcp-validate` |
| (`dbt/Dockerfile`, `WAREHOUSE=bigquery`) | `make gcp-images`: the dbt image for GCP (149 MiB stored, #206) built and pushed to `<region>-docker.pkg.dev/<project>/pplk8s/dbt:<DBT_IMAGE's version>`; `make gcp-image-check` runs it on the emulator first; Docker signs in through `docker-login.sh` | the local `dbt` image in the kind registry | live: `dbt:0.7.43` pushed 2026-11-02, the repository 157 MB |
| `infra/` | the one OpenTofu root: the free-path APIs, the kill switch, Artifact Registry's `pplk8s` Docker repository (two versions per image, scanning off; #230), the BigQuery datasets, workload service accounts and their grants, the daily query quota, Firestore's free database (#205); the model key's secret, the `scheduler` account, and, only while `images` names their images, the agent's Cloud Run service, the dbt Jobs and their Scheduler jobs (#209); `infra/tests/` plans them offline on a mock provider (`tofu test`) | Compose and kind; the kind registry (`localhost:5001`) | applied by the owner; #230's, #205's and #209's resources wait for `gcp-up` |
| `workloads.yaml` | the Cloud Run workloads' sizes, timeouts and schedules: the agent's service (1 vCPU, 512 MiB, 0 to `caps.cloud_run_max_instances`, CPU only during requests) and the Jobs `dbt-build` (daily, the platform part) and `dbt-source-freshness` (hourly, exit 0 on a stale source, JSON logs) on the dbt image as `dbt-runner` (#209) | the agent's Deployment, the dbt Job and the `source-freshness` CronJob in kind | in `make gcp-validate`; live: unverified |
| `access.yaml` | each workload's service account and the datasets it reads or writes, held to the lab's roles by `tests/test_access.py` | the warehouse roles of `dbt/macros/agent_warehouse.sql` | in `make gcp-validate` |
| `guardrails-check.sh` | `make gcp-guardrails-check`: reads back the daily query quota, the enabled APIs against the free path, Firestore's databases and the byte cap (#205); each Cloud Run service's instances, `cpuIdle`, invoker IAM and IAM members, each Job's tasks and retries, and the Scheduler job count (#209), skipped while their API is off | — | live: ok; #209's reads unverified |
| `tofu.sh` | `make gcp-plan`, `gcp-up`, `gcp-down`: credentials, the state at `gs://<project>-tfstate/default.tfstate` (no slash in the name: the cloud proxy breaks slashed object names), refuses without `GCP_PROJECT`; the workloads' images from `IMAGES`, else the ones Cloud Run runs now, so a plain plan or apply keeps them (#209) | — | applied; `gcp-plan`: no changes |
| `docker-login.sh` | `make gcp-images` signs Docker in to `<region>-docker.pkg.dev` before each push: a short-lived token of the signed-in gcloud account `tofu.sh` borrows, through `docker login` (a cloud session skips the login: its proxy injects the credential for that host, since 2026-11-02), no credential helper, so gcloud from Linux or from Windows (on WSL) both work (#289) | — | live: signed in and pushed from WSL 2026-11-02 |
| (`Makefile` `gcp-workloads-up`) | the owner's step: `gcp-images` (with its cost check), the apply that names the images, `dbt run-operation agent_warehouse` as an args override of the `dbt-build` Job, one `dbt-build` run, the cost check (#209) | `make workloads-up`, `make dbt-job` | live: unverified |
| `cost-check.sh` | `make gcp-cost-check`: the month's cost from the billing export, by service and SKU (#233) | — | live: no export rows yet |
| (dbt's `gcp` output, `tests/e2e/bigquery-run-check.sh`) | `make bigquery-live-check`: the emulator check on the lab project: its dbt datasets emptied, the fixture loaded by load jobs, the semantic path built and its metrics asserted against gold, then the bytes billed; the cost check before and after (#206) | `make bigquery-emulator-check` | live: passed 2026-11-01, 7.8 GiB billed, $0.00 |

## The $0.00 rule

- Use only what `free-path.yaml` lists; a new API or resource type joins it, with its source, in the PR that needs it, and `make gcp-validate` (in `make lint`) refuses anything else.
- Run `make gcp-cost-check` before and after every live step; exit 1 (a cost) or 3 (not provable yet) means no live GCP work until the owner says so.
- Dry-run a query before running it, and keep `maximum_bytes_billed` on every job; no streaming inserts (no free tier).
- Artifact Registry holds at most 0.5 GiB-month across the billing account: images go there only to be pulled by Cloud Run in us-central1, never pulled to a laptop or a cloud session (internet egress), and the Container Scanning and On-Demand Scanning APIs stay off (billed per image).
- Never raise a quota, a cap or the budget, and never test a permission by attempting the action: ask with `testIamPermissions`.
- Cloud Run serves only IAM callers (no public member, invoker IAM on) and bills per request: a public URL would spend the free requests and vCPU-seconds of anyone who finds it.
- Cloud sessions also carry claude-dotfiles' GCP kit (its `cloud/gcp/README.md`): a guard in front of every Bash command and a session-start line with the month-to-date cost.

## Identities

| Who | Roles on the project | Does |
|---|---|---|
| The owner, from their own signed-in shell | Owner | `make gcp-up` / `gcp-down`, enabling APIs, IAM, quotas, the budget |
| `pplk8s-automation`, the cloud sessions' credential (injected by the egress proxy, no key) | Viewer, BigQuery Job User and Data Editor, Service Usage Consumer; Storage Object Viewer on the state bucket; Artifact Registry Writer on the `pplk8s` repository (`infra/`) | reads, `make gcp-plan`, `make gcp-cost-check`, BigQuery work, pushing the lab's images (the proxy injects the credential for `us-central1-docker.pkg.dev` too, since 2026-11-02) |
| `dbt-runner`, `semantic-agent`, `agent-audit` (created by `infra/` from `access.yaml`) | BigQuery Job User; Data Editor on dbt's datasets and Data Viewer on `ds_source` (dbt), Data Viewer on `silver` and `semantic`, Cloud Datastore User (Firestore sessions), Service Account Token Creator on `agent-audit` only and Secret Accessor on the model key's secret only (the agent), none yet (the audit writer, whose insert-only grant on `ops.agent_queries` comes with the table, #209) | run the dbt Jobs, the agent's Cloud Run service and queries, the audit inserts (from #206 and #209) |
| `scheduler` (created by `infra/scheduler.tf`) | Cloud Run Invoker on the two scheduled Jobs only | Cloud Scheduler's OAuth identity when it runs `dbt-build` and `dbt-source-freshness` (#209) |
| `kill-switch` (created by `infra/`) | Project Billing Manager, Workflows Invoker, Eventarc Event Receiver, Logs Writer | unlinks billing when the budget passes `kill_switch_usd` |

The cloud sessions' credential holds no role that can enable an API, change IAM or quotas, or buy capacity, so a mistake there cannot spend; a product's role is added by the owner when an issue reaches it.

## Guard rails in place

- BigQuery query usage per day and per user: 31,457 MiB (`free-path.yaml` `caps`; set by hand in #226, imported and held by `infra/bigquery.tf`): 31 days of it stay under the free 1 TiB, and `make gcp-validate` fails a higher cap.
- Firestore: only the `(default)` database, which is the free one, with point-in-time recovery off; no TTL policies or backups (billed from the first byte).
- Cloud Run (#209): the agent's service scales from 0 to `caps.cloud_run_max_instances` (1) with CPU only during requests, inside the free 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million requests a month; each Job runs one task with no retry, and `make gcp-validate` holds the scheduled Jobs' worst month (every run for its whole timeout: 197,160 vCPU-seconds) under the Jobs' free 240,000.
- Cloud Scheduler: at most `caps.cloud_scheduler_jobs` (3, the billing account's free ones); the dbt Jobs take two, #228 the third.
- Secret Manager: one secret with one replica, its version added by hand; 6 active versions and 10,000 accesses a month are free.
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
   `make gcp-images` does too, and signs Docker in to Artifact Registry itself with that token, so it needs no `gcloud auth configure-docker` and works with either gcloud SDK; on WSL with the Windows SDK, `configure-docker` would register `docker-credential-gcloud.cmd`, which Linux Docker cannot run, so leave any `<region>-docker.pkg.dev` entry out of `credHelpers` in `~/.docker/config.json` (#289).
3. Connect the budget to the kill switch (console): Billing → Budgets & alerts → the lab's budget → Manage notifications → Connect a Pub/Sub topic → the project's `budget-alerts` → Save.
4. Check: `GCP_PROJECT=$P make gcp-plan` from a cloud session shows no changes; the workflow's executions (Workflows → `kill-switch`) end after one step.
5. The agent's model key (once, after the `gcp-up` that creates its secret): add the OpenRouter key's secret version by hand, so it never enters the OpenTofu state, and keep one version enabled (six are free):

```bash
read -rs KEY && printf '%s' "$KEY" | gcloud secrets versions add openrouter-api-key --project="$P" --data-file=- && unset KEY
```

6. The workloads (#209): `make gcp-cost-check`, then `GCP_PROJECT=$P make gcp-workloads-up` (`gcp-images` signs Docker in itself), then `make gcp-guardrails-check` and `make gcp-cost-check`; a question goes through `gcloud run services proxy semantic-agent --region=us-central1 --project="$P"`, which signs each request as the gcloud account.

When the lab ends: `make gcp-down`, then delete the project.
