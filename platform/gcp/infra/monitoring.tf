# The source-freshness alert (#209): the stand-in for SourceStale, the Prometheus rule on the warehouse's
# sql_exporter (semantic/PLAN.md SL-12). The dbt-source-freshness Job runs `dbt source freshness` hourly with JSON
# logs and exits 0 on a stale source, so the alert reads the verdicts, not the Job's status: Cloud Run turns each
# JSON line of its output into a log entry's jsonPayload, and a log-based metric counts dbt's LogFreshnessResult
# events whose status is `error` (past error_after) or `runtime error` (the check could not run, say the table is
# gone), one time series per table and status. A threshold policy opens one incident per stale table and keeps it
# open while every hourly run finds the table stale; it closes once a run finds it fresh.
# All three exist only while the Job does (var.images names the dbt image, infra/run.tf).
# Cost: the metric is a chargeable custom metric, 8 bytes a point and at most a point a minute per series, inside
# Monitoring's free 150 MiB a month (free-path.yaml `caps.log_metric_series`); the email channel bills nothing;
# alerting is free until Cloud Monitoring charges for it, no sooner than 2027-09-01 (free-path.yaml `until`).

locals {
  freshness_job   = "dbt-source-freshness"
  freshness_alert = contains(keys(local.jobs), local.freshness_job)
}

# The address that receives the alert: tofu.sh passes the signed-in gcloud account, else the deployed channel's
# address, so it is never committed; a plan with neither (a cloud session before the first apply) has no channel.
variable "alert_email" {
  description = "Where the freshness alert is sent (tofu.sh: ALERT_EMAIL, the active gcloud account, or the deployed channel's address)."
  type        = string
  default     = null

  validation {
    condition     = var.alert_email == null || can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.alert_email))
    error_message = "alert_email is an email address."
  }
}

# The filter's fields and values are dbt-core 1.12's JSON log format (dbt/events/types.py LogFreshnessResult,
# code Q018), held against a line captured from `dbt source freshness` on the BigQuery emulator by
# platform/gcp/tests/test_freshness_alert.py. `info.name` matters: dbt's RunResultErrorNoMessage carries
# `data.status: error` for the same table, and would count it twice.
resource "google_logging_metric" "stale_source" {
  count = local.freshness_alert ? 1 : 0

  name        = "dbt-source-freshness-errors"
  description = "dbt source freshness verdicts of error or runtime error from the dbt-source-freshness Cloud Run Job, by source table (#209)."
  filter      = <<-EOT
    resource.type="cloud_run_job"
    resource.labels.job_name="dbt-source-freshness"
    jsonPayload.info.name="LogFreshnessResult"
    jsonPayload.data.status=("error" OR "runtime error")
  EOT

  metric_descriptor {
    metric_kind  = "DELTA"
    value_type   = "INT64"
    unit         = "1"
    display_name = "dbt source freshness errors"

    labels {
      key         = "source"
      description = "The dbt source (ds_source)."
    }
    labels {
      key         = "table"
      description = "The source table found stale."
    }
    labels {
      key         = "status"
      description = "error (past error_after) or runtime error (the check could not run)."
    }
  }

  label_extractors = {
    source = "EXTRACT(jsonPayload.data.source_name)"
    table  = "EXTRACT(jsonPayload.data.table_name)"
    status = "EXTRACT(jsonPayload.data.status)"
  }

  lifecycle {
    precondition {
      condition     = lookup(local.jobs[local.freshness_job].env, "DBT_LOG_FORMAT", "") == "json"
      error_message = "The metric reads dbt's JSON logs: the freshness Job needs DBT_LOG_FORMAT=json (workloads.yaml)."
    }
  }
}

resource "google_monitoring_notification_channel" "email" {
  count = local.freshness_alert && var.alert_email != null ? 1 : 0

  display_name = "pplk8s lab owner"
  description  = "The lab project's owner, for the source-freshness alert (#209)."
  type         = "email"
  labels = {
    email_address = var.alert_email
  }
}

resource "google_monitoring_alert_policy" "stale_source" {
  count = local.freshness_alert ? 1 : 0

  display_name          = "A dbt source is stale"
  combiner              = "OR"
  severity              = "WARNING"
  notification_channels = google_monitoring_notification_channel.email[*].name

  conditions {
    display_name = "dbt source freshness error, per table"

    condition_threshold {
      filter = "resource.type = \"cloud_run_job\" AND metric.type = \"logging.googleapis.com/user/${google_logging_metric.stale_source[0].name}\""
      # The Job runs hourly, so a window of 90 minutes always holds the latest run's verdict: an incident opens on
      # the first stale run and stays open, one per table, until a run finds the table fresh and the window empties.
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      # Not 0s: the API refuses evaluation_missing_data on a zero duration. The window holds a stale run's count
      # for 90 minutes, so holding it a minute only opens the incident a minute later.
      duration = "60s"

      aggregations {
        alignment_period     = "5400s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["metric.label.table"]
      }

      trigger {
        count = 1
      }

      # No error in the window is no data, which closes the incident.
      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"
    }
  }

  alert_strategy {
    auto_close           = "1800s"
    notification_prompts = ["OPENED", "CLOSED"]
  }

  documentation {
    subject   = "pplk8s: dbt source $${metric.label.table} is stale"
    mime_type = "text/markdown"
    content   = <<-EOT
      The hourly `dbt-source-freshness` Job found `$${metric.label.table}` past its `error_after`, or could not check it.
      Each table's verdict and newest load are in `ops.source_freshness`; the Job's log holds dbt's message.
      The products that read the table answer with stale freshness until its pipeline lands again (#209).
    EOT
  }
}

# An alert nobody receives still opens incidents in the console; a warning, not an error, so a cloud session
# without the owner's address can still plan.
check "freshness_alert_reaches_someone" {
  assert {
    condition     = !local.freshness_alert || var.alert_email != null
    error_message = "The freshness alert has no notification channel: sign in to gcloud or set ALERT_EMAIL before gcp-up."
  }
}
