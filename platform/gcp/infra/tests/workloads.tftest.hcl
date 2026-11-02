# `make gcp-validate`, offline (a mock provider, no credentials): the workloads of run.tf and scheduler.tf
# exist only while var.images names their images, with the caps and identities #209 sets.

mock_provider "google" {
  mock_resource "google_service_account" {
    defaults = {
      name  = "projects/lab-project/serviceAccounts/mock-account@lab-project.iam.gserviceaccount.com"
      email = "mock-account@lab-project.iam.gserviceaccount.com"
    }
  }
}

variables {
  project = "lab-project"
}

run "a_plain_gcp_up_has_no_workloads" {
  command = plan

  assert {
    condition     = length(google_cloud_run_v2_service.workload) + length(google_cloud_run_v2_job.workload) + length(google_cloud_scheduler_job.run_job) == 0
    error_message = "Without images, gcp-up creates (or keeps) no Cloud Run workload and no Scheduler job."
  }

  assert {
    condition     = google_secret_manager_secret.openrouter_key.secret_id == "openrouter-api-key"
    error_message = "The key's secret exists before the agent, so the owner can add its version first."
  }
}

run "the_agent_alone" {
  command = plan

  variables {
    images = { semantic-agent = "us-central1-docker.pkg.dev/lab-project/pplk8s/semantic-agent:abc" }
  }

  assert {
    condition     = keys(google_cloud_run_v2_service.workload) == ["semantic-agent"] && length(google_cloud_run_v2_job.workload) == 0 && length(google_cloud_scheduler_job.run_job) == 0
    error_message = "The agent's image makes the service only."
  }
}

run "both_images" {
  command = plan

  variables {
    images = {
      semantic-agent = "us-central1-docker.pkg.dev/lab-project/pplk8s/semantic-agent:abc"
      dbt            = "us-central1-docker.pkg.dev/lab-project/pplk8s/dbt:def"
    }
  }

  assert {
    condition     = keys(google_cloud_run_v2_job.workload) == ["dbt-build", "dbt-source-freshness"] && keys(google_cloud_scheduler_job.run_job) == ["dbt-build", "dbt-source-freshness"]
    error_message = "Two Jobs, each on its Scheduler job."
  }

  assert {
    condition = alltrue([
      google_cloud_run_v2_service.workload["semantic-agent"].template[0].scaling[0].min_instance_count == 0,
      google_cloud_run_v2_service.workload["semantic-agent"].template[0].scaling[0].max_instance_count == 1,
      google_cloud_run_v2_service.workload["semantic-agent"].template[0].containers[0].resources[0].cpu_idle,
      !google_cloud_run_v2_service.workload["semantic-agent"].invoker_iam_disabled,
    ])
    error_message = "The service bills per request: 0 to 1 instances, CPU only during requests, IAM callers only."
  }

  assert {
    condition = toset(["AGENT_WAREHOUSE", "GCP_PROJECT", "BQ_MAXIMUM_BYTES_BILLED", "AUDIT_SERVICE_ACCOUNT", "SESSION_SERVICE_URI", "MODEL_BACKEND", "OPENROUTER_API_KEY"]) == setintersection(
      toset([for e in google_cloud_run_v2_service.workload["semantic-agent"].template[0].containers[0].env : e.name]),
      toset(["AGENT_WAREHOUSE", "GCP_PROJECT", "BQ_MAXIMUM_BYTES_BILLED", "AUDIT_SERVICE_ACCOUNT", "SESSION_SERVICE_URI", "MODEL_BACKEND", "OPENROUTER_API_KEY"]),
    )
    error_message = "The agent gets the BigQuery seam's settings, the Firestore sessions, the model's and its key."
  }

  assert {
    condition = alltrue([for j in google_cloud_run_v2_job.workload : alltrue([
      j.template[0].task_count == 1,
      j.template[0].parallelism == 1,
      j.template[0].template[0].max_retries == 0,
    ])])
    error_message = "One task, one attempt per run: the free-tier budget counts one instance per run."
  }

  assert {
    condition     = google_cloud_run_v2_job.workload["dbt-source-freshness"].template[0].template[0].containers[0].command[2] == "dbt source freshness; rc=$?; [ \"$rc\" -le 1 ]"
    error_message = "The freshness Job exits 0 on a stale source, as the kind CronJob does."
  }

  assert {
    condition     = google_cloud_scheduler_job.run_job["dbt-build"].http_target[0].uri == "https://run.googleapis.com/v2/projects/lab-project/locations/us-central1/jobs/dbt-build:run"
    error_message = "Scheduler calls the Run Admin API's run method."
  }
}

run "an_image_from_elsewhere_is_refused" {
  command = plan

  variables {
    images = { dbt = "docker.io/library/dbt:latest" }
  }

  expect_failures = [google_cloud_run_v2_job.workload]
}
