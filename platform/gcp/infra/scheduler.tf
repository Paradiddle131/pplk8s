# Cloud Scheduler runs each scheduled Job of platform/gcp/workloads.yaml (#209): the stand-in for the kind
# CronJob and the DAGs' dbt runs. Three jobs a month are free per billing account, not per project
# (free-path.yaml `caps.cloud_scheduler_jobs`); these take two and leave one for the orchestration of #228.
# Each calls the Cloud Run Admin API's run method as the `scheduler` account, which may run those Jobs only.
# One resource over the yaml's schedules, so check_free_path.py counts every Scheduler job there.

resource "google_service_account" "scheduler" {
  account_id   = "scheduler"
  display_name = "Runs the lab's scheduled Cloud Run Jobs"
  depends_on   = [google_project_service.free_path]
}

locals {
  scheduled = { for name, j in local.jobs : name => j if lookup(j, "schedule", null) != null }
}

# Cloud Run Invoker on the Job: run.jobs.run, without overrides, and nothing on the project.
resource "google_cloud_run_v2_job_iam_member" "scheduler" {
  for_each = local.scheduled

  location = var.region
  name     = google_cloud_run_v2_job.workload[each.key].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "run_job" {
  for_each = local.scheduled

  name      = each.key
  region    = var.region
  schedule  = each.value.schedule
  time_zone = "Etc/UTC"
  # A job marked `paused` in workloads.yaml exists but does not fire (the freshness check until #227).
  paused = lookup(each.value, "paused", false)
  # The Admin API answers as soon as the execution starts; the Job's own timeout bounds the run.
  attempt_deadline = "60s"

  # The next scheduled run is the retry, as for the Job itself.
  retry_config {
    retry_count = 0
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project}/locations/${var.region}/jobs/${google_cloud_run_v2_job.workload[each.key].name}:run"

    # The default scope, cloud-platform; the token is the `scheduler` account's.
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler]
}
