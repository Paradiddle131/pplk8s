# BigQuery on the lab project (#205): the datasets dbt builds, one service account per workload with
# dataset-level grants and, on the `ops` tables that exist, table-level ones (platform/gcp/access.yaml, #209),
# and the daily query quota that is the hard stop.
# Storage is free up to 10 GiB and queries up to 1 TiB a month; load jobs and DML are free, streaming
# inserts are not (platform/gcp/README.md).

locals {
  access = yamldecode(file("${path.module}/../access.yaml"))
  caps   = local.free_path.caps

  dataset_grants = merge(
    { for pair in flatten([
      for sa, a in local.access.service_accounts : [for ds in a.reads : { sa = sa, ds = ds }]
    ]) : "${pair.sa}/${pair.ds}" => merge(pair, { role = "roles/bigquery.dataViewer" }) },
    { for pair in flatten([
      for sa, a in local.access.service_accounts : [for ds in a.writes : { sa = sa, ds = ds }]
    ]) : "${pair.sa}/${pair.ds}" => merge(pair, { role = "roles/bigquery.dataEditor" }) },
  )

  # access.yaml `tables:`, each access its `table_access` role: a predefined one, or the custom role below.
  table_roles = {
    for access, a in local.access.table_access : access => (
      can(a.role) ? a.role : "projects/${var.project}/roles/${google_project_iam_custom_role.table_access[access].role_id}"
    )
  }
  table_grants = { for pair in flatten([
    for sa, a in local.access.service_accounts : [
      for table, access in lookup(a, "tables", {}) : {
        sa = sa, ds = split(".", table)[0], table = split(".", table)[1], role = local.table_roles[access]
      }
    ]
  ]) : "${pair.sa}/${pair.ds}.${pair.table}" => pair if pair.ds == "ops" && contains(var.existing_ops_tables, pair.table) }
}

# dbt's run-operations create the `ops` tables (`agent_warehouse`), so a table grant waits for its table: tofu.sh
# lists the dataset, and a fresh project plans without them instead of failing on a table not there yet.
variable "existing_ops_tables" {
  description = "The tables in the `ops` dataset now (tofu.sh lists them): access.yaml's table grants apply to these only."
  type        = list(string)
  default     = []
}

# The datasets on the project now (tofu.sh lists them): one made by hand before it was declared here is imported.
variable "existing_datasets" {
  description = "The project's BigQuery datasets now (tofu.sh lists them), imported when declared but not yet in the state."
  type        = list(string)
  default     = []
}

import {
  for_each = { for ds, _ in local.access.datasets : ds => ds if contains(var.existing_datasets, ds) }
  to       = google_bigquery_dataset.layer[each.key]
  id       = "projects/${var.project}/datasets/${each.value}"
}

resource "google_bigquery_dataset" "layer" {
  for_each = local.access.datasets

  dataset_id  = each.key
  location    = "US"
  description = each.value
  labels      = { layer = replace(each.key, "_", "-") }
  # `make gcp-down` removes the lab in one step; the data is synthetic and rebuilt by dbt.
  delete_contents_on_destroy = true

  depends_on = [google_project_service.free_path]
}

resource "google_service_account" "workload" {
  for_each = local.access.service_accounts

  account_id   = each.key
  display_name = each.value.description
  depends_on   = [google_project_service.free_path]
}

# Every workload runs its own query jobs in the project; what it may read or write is the dataset grants.
resource "google_project_iam_member" "job_user" {
  for_each = local.access.service_accounts

  project = var.project
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.workload[each.key].email}"
}

resource "google_bigquery_dataset_iam_member" "grant" {
  for_each = local.dataset_grants

  dataset_id = google_bigquery_dataset.layer[each.value.ds].dataset_id
  role       = each.value.role
  member     = "serviceAccount:${google_service_account.workload[each.value.sa].email}"
}

# access.yaml `table_access` given as permissions: a project custom role each (IAM roles are free), granted only on
# tables. A deleted custom role stays soft-deleted: the provider undeletes it on a re-create within 7 days, but its
# id is taken for up to 37, so a gcp-down and gcp-up 7 to 37 days apart needs the role's id changed.
resource "google_project_iam_custom_role" "table_access" {
  for_each = { for access, a in local.access.table_access : access => a if can(a.permissions) }

  role_id     = "pplk8sTable${title(each.key)}"
  title       = "pplk8s table ${each.key}"
  description = "The lab's `${each.key}` access to one BigQuery table (platform/gcp/access.yaml, #209)."
  permissions = each.value.permissions

  depends_on = [google_project_service.free_path]
}

resource "google_bigquery_table_iam_member" "grant" {
  for_each = local.table_grants

  dataset_id = google_bigquery_dataset.layer[each.value.ds].dataset_id
  table_id   = each.value.table
  role       = each.value.role
  member     = "serviceAccount:${google_service_account.workload[each.value.sa].email}"
}

# The hard stop on query spend: bytes a day for the project and for each user, in MiB. 31 days of it stay
# under the free 1 TiB a month (check_free_path.py), so no month can bill a query; never raised.
# Quota preferences cannot be deleted, so tofu.sh passes the ones that exist (created in the console,
# #226, or by an earlier gcp-up) and they are imported, not created twice; `make gcp-down` leaves them in place.
# Cloud Run's (infra/run.tf) come the same way.
variable "existing_quota_preferences" {
  description = "`<service>/<quota id>` => name of the quota preferences already on the project, global or in var.region (tofu.sh reads them)."
  type        = map(string)
  default     = {}
}

locals {
  bigquery_query_quotas = toset(["QueryUsagePerDay", "QueryUsagePerUserPerDay"])
  # Only the quotas declared here: an import needs its target in the configuration.
  bigquery_quota_preferences = {
    for key, name in var.existing_quota_preferences : split("/", key)[1] => name
    if split("/", key)[0] == "bigquery.googleapis.com" && contains(local.bigquery_query_quotas, split("/", key)[1])
  }
}

import {
  for_each = local.bigquery_quota_preferences
  to       = google_cloud_quotas_quota_preference.bigquery_query[each.key]
  id       = "projects/${var.project}/locations/global/quotaPreferences/${each.value}"
}

resource "google_cloud_quotas_quota_preference" "bigquery_query" {
  for_each = local.bigquery_query_quotas

  parent        = "projects/${var.project}"
  name          = lookup(local.bigquery_quota_preferences, each.key, lower("bigquery-${each.key}"))
  service       = "bigquery.googleapis.com"
  quota_id      = each.key
  justification = "The lab project stays inside BigQuery's free 1 TiB of queries a month (semantic/PLAN.md SL-13)."

  quota_config {
    preferred_value = tostring(local.caps.bigquery_query_mib_per_day)
  }

  depends_on = [google_project_service.free_path]
}

output "service_accounts" {
  description = "The workloads' service accounts, by workload."
  value       = { for k, sa in google_service_account.workload : k => sa.email }
}
