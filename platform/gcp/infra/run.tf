# The lab's workloads on Cloud Run (#209), sized and scheduled by platform/gcp/workloads.yaml: the agent's
# service and the dbt image's Jobs. Each exists only while var.images names its image (tofu.sh passes the
# deployed ones, `make gcp-workloads-up` new ones), so a plain `make gcp-up` neither creates nor removes them.
# The service bills per request: request-based billing (CPU only while a request runs), 0 instances when idle,
# at most free-path.yaml's cap; only IAM-authorised callers reach it (no public member, invoker IAM on).
# Cloud Run's free tier per billing account a month: 180,000 vCPU-seconds, 360,000 GiB-seconds and 2 million
# requests for request-billed services; 240,000 vCPU-seconds and 450,000 GiB-seconds for Jobs, which bill each
# instance's whole life, at least a minute (check_free_path.py holds the Jobs' worst case to it).

locals {
  workloads = yamldecode(file("${path.module}/../workloads.yaml"))
  registry  = "${var.region}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.images.repository_id}/"
  services  = { for name, s in local.workloads.services : name => s if contains(keys(var.images), s.image) }
  jobs      = { for name, j in local.workloads.jobs : name => j if contains(keys(var.images), j.image) }

  # The agent's model settings are the kind stand-in's (one place: the ConfigMap), its key Secret Manager's.
  agent_model_env = yamldecode(file("${path.module}/../../k8s/workloads/semantic-agent-configmap.yaml")).data
  # ADK's Firestore session service keeps every session under this root collection of the free (default) database.
  session_collection = "agent-sessions"
  agent_env = merge(local.agent_model_env, {
    AGENT_WAREHOUSE         = "bigquery"
    DBT_TARGET              = "gcp"
    GCP_PROJECT             = var.project
    BQ_MAXIMUM_BYTES_BILLED = tostring(local.caps.bigquery_maximum_bytes_billed)
    AUDIT_SERVICE_ACCOUNT   = google_service_account.workload["agent-audit"].email
    # `firestore://` with no host is the free (default) database: the agent's services.py reads a host as a
    # database name, so the collection goes in ADK's own variable below, never in the URI.
    SESSION_SERVICE_URI           = "firestore://"
    ADK_FIRESTORE_ROOT_COLLECTION = local.session_collection
  })
}

resource "google_cloud_run_v2_service" "workload" {
  for_each = local.services

  name     = each.key
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"
  # Every request needs a caller holding run.routes.invoke (the owner; `gcloud run services proxy`).
  invoker_iam_disabled = false
  # `make gcp-down` removes the lab in one step; the provider's default would refuse.
  deletion_protection = false

  template {
    service_account                  = google_service_account.workload[each.value.service_account].email
    timeout                          = "${each.value.timeout_s}s"
    max_instance_request_concurrency = each.value.concurrency

    scaling {
      min_instance_count = 0
      max_instance_count = local.caps.cloud_run_max_instances
    }

    containers {
      image = var.images[each.value.image]

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = tostring(each.value.cpu)
          memory = each.value.memory
        }
        # Request-based billing: CPU only while a request runs. No startup boost (billed CPU at every start).
        cpu_idle          = true
        startup_cpu_boost = false
      }

      dynamic "env" {
        for_each = local.agent_env
        content {
          name  = env.key
          value = env.value
        }
      }

      env {
        name = "OPENROUTER_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.openrouter_key.secret_id
            version = "latest"
          }
        }
      }

      # ADK loads the agent and MetricFlow, and the GCP image builds its catalog, before serving.
      startup_probe {
        http_get {
          path = "/list-apps"
        }
        period_seconds    = 5
        failure_threshold = 48
        timeout_seconds   = 3
      }
    }
  }

  lifecycle {
    precondition {
      condition     = startswith(var.images[each.value.image], local.registry)
      error_message = "Cloud Run pulls for free only from the lab's own repository in ${var.region}: ${local.registry}"
    }
  }

  depends_on = [google_secret_manager_secret_iam_member.agent_key]
}

resource "google_cloud_run_v2_job" "workload" {
  for_each = local.jobs

  name     = each.key
  location = var.region
  # `make gcp-down` removes the lab in one step; the provider's default would refuse.
  deletion_protection = false

  template {
    # One task, one attempt: the next scheduled run is the retry (the kind CronJob's backoffLimit 0), and the
    # free-tier budget of check_free_path.py counts one instance per run.
    task_count  = 1
    parallelism = 1

    template {
      service_account = google_service_account.workload[each.value.service_account].email
      timeout         = "${each.value.timeout_s}s"
      max_retries     = 0

      containers {
        image   = var.images[each.value.image]
        command = lookup(each.value, "command", null)
        args    = lookup(each.value, "args", null)

        resources {
          limits = {
            cpu    = tostring(each.value.cpu)
            memory = each.value.memory
          }
        }

        # dbt's `gcp` output reads the project from GCP_PROJECT and authenticates as the Job's service account.
        dynamic "env" {
          for_each = merge(each.value.env, { GCP_PROJECT = var.project })
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  lifecycle {
    precondition {
      condition     = startswith(var.images[each.value.image], local.registry)
      error_message = "Cloud Run pulls for free only from the lab's own repository in ${var.region}: ${local.registry}"
    }
  }
}

# The agent's grants beyond BigQuery (infra/bigquery.tf), held whether or not it is deployed:
# its ADK sessions in Firestore's one database, and its audit insert run as `agent-audit` by impersonation
# (services/semantic-agent: AUDIT_SERVICE_ACCOUNT), a token it may mint for that one account only.
resource "google_project_iam_member" "agent_sessions" {
  project = var.project
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.workload["semantic-agent"].email}"
}

resource "google_service_account_iam_member" "agent_impersonates_audit" {
  service_account_id = google_service_account.workload["agent-audit"].name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.workload["semantic-agent"].email}"
}

# Cloud Run's regional quotas in var.region, lowered to free-path.yaml's `caps.cloud_run_regional_quotas` (#209):
# a stop on how many instances, vCPUs and bytes of memory may run at once, whatever a deploy or a console edit asks
# (the services' own max_instance_count is the first stop). Held whether or not a workload is deployed. A quota
# with no `quota_id` yet (free-path.yaml's TODO) gets no preference. Quota preferences cannot be deleted: tofu.sh
# passes the ones on the project and they are imported (infra/bigquery.tf's variable), never created twice.
locals {
  run_quotas = { for metric, q in local.caps.cloud_run_regional_quotas : metric => q if q.quota_id != null }
  run_quota_preferences = {
    for metric, q in local.run_quotas : metric => var.existing_quota_preferences["run.googleapis.com/${q.quota_id}"]
    if contains(keys(var.existing_quota_preferences), "run.googleapis.com/${q.quota_id}")
  }
}

import {
  for_each = local.run_quota_preferences
  to       = google_cloud_quotas_quota_preference.cloud_run[each.key]
  id       = "projects/${var.project}/locations/global/quotaPreferences/${each.value}"
}

resource "google_cloud_quotas_quota_preference" "cloud_run" {
  for_each = local.run_quotas

  parent        = "projects/${var.project}"
  name          = lookup(local.run_quota_preferences, each.key, lower("run-${each.value.quota_id}-${var.region}"))
  service       = "run.googleapis.com"
  quota_id      = each.value.quota_id
  dimensions    = { region = var.region }
  justification = "The lab project caps what Cloud Run may run at once, inside its free tier (semantic/PLAN.md SL-13)."
  # Lowering a default of 100 instances to a handful is a decrease of more than 10%, which the API refuses
  # unless told it is meant; this preference only ever lowers (check_free_path.py).
  ignore_safety_checks = "QUOTA_DECREASE_PERCENTAGE_TOO_HIGH"

  quota_config {
    preferred_value = tostring(each.value.value)
  }

  lifecycle {
    # A flag on the request, not a property of the preference: an imported one would otherwise plan an update.
    ignore_changes = [ignore_safety_checks]
  }

  depends_on = [google_project_service.free_path]
}

output "agent_url" {
  description = "The agent's Cloud Run URL (IAM callers only: `gcloud run services proxy semantic-agent`), or null without its image."
  value       = try(google_cloud_run_v2_service.workload["semantic-agent"].uri, null)
}
