# `make gcp-validate`, offline (a mock provider, no credentials): the freshness alert exists only with the
# freshness Job, and its channel only with an address; table grants only on the ops tables that exist, the
# insert one a custom role; Cloud Run's three regional quota preferences (#209).

mock_provider "google" {
  mock_resource "google_service_account" {
    defaults = {
      name  = "projects/lab-project/serviceAccounts/mock-account@lab-project.iam.gserviceaccount.com"
      email = "mock-account@lab-project.iam.gserviceaccount.com"
    }
  }
  mock_resource "google_monitoring_notification_channel" {
    defaults = {
      name = "projects/lab-project/notificationChannels/123"
    }
  }
}

variables {
  project = "lab-project"
}

run "no_freshness_job_no_alert" {
  command = plan

  variables {
    images      = { semantic-agent = "us-central1-docker.pkg.dev/lab-project/pplk8s/semantic-agent:abc" }
    alert_email = "owner@example.com"
  }

  assert {
    condition     = length(google_logging_metric.stale_source) + length(google_monitoring_alert_policy.stale_source) + length(google_monitoring_notification_channel.email) == 0
    error_message = "Without the dbt image there is no freshness Job, so no metric, policy or channel."
  }

  assert {
    condition     = length(google_bigquery_table_iam_member.grant) == 0
    error_message = "A fresh project has no ops tables, so no table grant is planned."
  }

  assert {
    condition = join(",", sort([for p in google_cloud_quotas_quota_preference.cloud_run : "${p.quota_id}=${p.quota_config[0].preferred_value}"])) == "CpuAllocPerProjectRegion=4000,InstancesPerProject=4,MemAllocPerProjectRegion=2147483648" && alltrue([
      for p in google_cloud_quotas_quota_preference.cloud_run : p.service == "run.googleapis.com" && p.dimensions.region == "us-central1"
    ])
    error_message = "Cloud Run's three regional quotas lowered in us-central1, whether or not a workload is deployed."
  }
}

run "the_alert_with_its_channel" {
  command = apply

  variables {
    images      = { dbt = "us-central1-docker.pkg.dev/lab-project/pplk8s/dbt:def" }
    alert_email = "owner@example.com"
  }

  assert {
    condition     = google_monitoring_notification_channel.email[0].type == "email" && google_monitoring_notification_channel.email[0].labels.email_address == "owner@example.com"
    error_message = "One email channel to the address tofu.sh passes."
  }

  assert {
    condition     = one(google_monitoring_alert_policy.stale_source[0].notification_channels) == "projects/lab-project/notificationChannels/123"
    error_message = "The policy notifies the email channel."
  }

  assert {
    condition     = strcontains(google_logging_metric.stale_source[0].filter, "resource.labels.job_name=\"dbt-source-freshness\"") && join(",", keys(google_logging_metric.stale_source[0].label_extractors)) == "source,status,table"
    error_message = "The metric reads the freshness Job's log, one series per source, table and status."
  }

  assert {
    condition = alltrue([
      google_monitoring_alert_policy.stale_source[0].conditions[0].condition_threshold[0].comparison == "COMPARISON_GT",
      google_monitoring_alert_policy.stale_source[0].conditions[0].condition_threshold[0].threshold_value == 0,
      one(google_monitoring_alert_policy.stale_source[0].conditions[0].condition_threshold[0].aggregations[0].group_by_fields) == "metric.label.table",
      tonumber(trimsuffix(google_monitoring_alert_policy.stale_source[0].conditions[0].condition_threshold[0].aggregations[0].alignment_period, "s")) > 3600,
      google_monitoring_alert_policy.stale_source[0].alert_strategy[0].auto_close != null,
    ])
    error_message = "Count above 0 per table over a window longer than the hourly schedule, closing on its own."
  }
}

run "a_plan_without_an_address_has_no_channel" {
  command = plan

  variables {
    images = { dbt = "us-central1-docker.pkg.dev/lab-project/pplk8s/dbt:def" }
  }

  assert {
    condition     = length(google_monitoring_alert_policy.stale_source) == 1 && length(google_monitoring_notification_channel.email) == 0
    error_message = "A cloud session's plan without the owner's address plans the policy and no channel (the check warns)."
  }

  # The check block's warning, not an error: the plan still succeeds.
  expect_failures = [check.freshness_alert_reaches_someone]
}

run "table_grants_wait_for_their_tables" {
  command = plan

  variables {
    existing_ops_tables = ["agent_queries", "readiness", "source_freshness"]
  }

  assert {
    condition     = keys(google_bigquery_table_iam_member.grant) == ["agent-audit/ops.agent_queries", "semantic-agent/ops.readiness"]
    error_message = "Grants on the existing tables access.yaml names, and none on product_deadlines before it exists."
  }

  assert {
    condition = alltrue([
      google_bigquery_table_iam_member.grant["agent-audit/ops.agent_queries"].role == "projects/lab-project/roles/pplk8sTableInsert",
      google_bigquery_table_iam_member.grant["semantic-agent/ops.readiness"].role == "roles/bigquery.dataViewer",
      google_bigquery_table_iam_member.grant["agent-audit/ops.agent_queries"].table_id == "agent_queries",
    ])
    error_message = "The audit writer's insert is the custom role on its one table; the agent reads."
  }

  assert {
    condition     = join(",", keys(google_project_iam_custom_role.table_access)) == "insert" && join(",", sort(google_project_iam_custom_role.table_access["insert"].permissions)) == "bigquery.tables.get,bigquery.tables.updateData"
    error_message = "One custom role, holding only what a DML INSERT ... VALUES needs on its target table."
  }
}

run "a_bad_address_is_refused" {
  command = plan

  variables {
    alert_email = "not an address"
  }

  expect_failures = [var.alert_email]
}
