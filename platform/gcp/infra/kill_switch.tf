# The kill switch (platform/gcp/README.md): the owner's budget publishes to this topic several times a
# day; Eventarc hands each message to a workflow that unlinks billing from the project once the
# month-to-date cost passes var.kill_switch_usd. Pub/Sub, Eventarc (Pub/Sub source) and Workflows
# (about one step per notification) stay inside their free tiers; nothing is built or stored.
# Unlinking billing shuts every resource down and may delete some, hence a threshold far above the first cent.

resource "google_pubsub_topic" "budget" {
  name       = "budget-alerts"
  depends_on = [google_project_service.free_path]
}

resource "google_service_account" "kill_switch" {
  account_id   = "kill-switch"
  display_name = "Unlinks billing when the budget passes the kill-switch threshold"
  depends_on   = [google_project_service.free_path]
}

# Project Billing Manager on this project only: enough to unlink its billing, nothing on the billing account.
resource "google_project_iam_member" "kill_switch" {
  for_each = toset([
    "roles/billing.projectManager",
    "roles/workflows.invoker",
    "roles/eventarc.eventReceiver",
    "roles/logging.logWriter",
  ])

  project = var.project
  role    = each.value
  member  = "serviceAccount:${google_service_account.kill_switch.email}"
}

resource "google_workflows_workflow" "kill_switch" {
  name            = "kill-switch"
  region          = var.region
  description     = "Unlink billing from ${var.project} once the budget's month-to-date cost passes ${var.kill_switch_usd} USD."
  service_account = google_service_account.kill_switch.id
  call_log_level  = "LOG_ERRORS_ONLY"
  source_contents = templatefile("${path.module}/kill_switch.workflow.yaml", {
    project   = var.project
    threshold = var.kill_switch_usd
  })
  depends_on = [google_project_service.free_path]
}

resource "google_eventarc_trigger" "kill_switch" {
  name            = "kill-switch"
  location        = var.region
  service_account = google_service_account.kill_switch.email

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.pubsub.topic.v1.messagePublished"
  }

  destination {
    workflow = google_workflows_workflow.kill_switch.id
  }

  transport {
    pubsub {
      topic = google_pubsub_topic.budget.id
    }
  }

  depends_on = [google_project_iam_member.kill_switch]
}

output "budget_topic" {
  description = "Connect the budget to this topic (platform/gcp/README.md, the owner's steps)."
  value       = google_pubsub_topic.budget.id
}
