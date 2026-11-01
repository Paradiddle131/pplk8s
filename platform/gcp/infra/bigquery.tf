# BigQuery on the lab project (#205): the datasets dbt builds, one service account per workload with
# dataset-level grants (platform/gcp/access.yaml), and the daily query quota that is the hard stop.
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

# The hard stop on query spend: bytes a day for the project and for each user, in MiB. 31 days of it stay
# under the free 1 TiB a month (check_free_path.py), so no month can bill a query; never raised.
# Quota preferences cannot be deleted, so tofu.sh passes the ones that exist (created in the console,
# #226) and they are imported, not created twice; `make gcp-down` leaves them in place.
variable "existing_quota_preferences" {
  description = "Quota id => name of the BigQuery quota preferences already on the project (tofu.sh reads them)."
  type        = map(string)
  default     = {}
}

import {
  for_each = var.existing_quota_preferences
  to       = google_cloud_quotas_quota_preference.bigquery_query[each.key]
  id       = "projects/${var.project}/locations/global/quotaPreferences/${each.value}"
}

resource "google_cloud_quotas_quota_preference" "bigquery_query" {
  for_each = toset(["QueryUsagePerDay", "QueryUsagePerUserPerDay"])

  parent        = "projects/${var.project}"
  name          = lookup(var.existing_quota_preferences, each.key, lower("bigquery-${each.key}"))
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
