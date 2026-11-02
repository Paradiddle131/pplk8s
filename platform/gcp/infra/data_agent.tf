# The data agent's conversation logs (BigQuery Agent Analytics; #207): each turn of the data agent's conversations,
# its prompt, answer, user and session ids, latency, tokens and errors, streamed by Google's Gemini Data Analytics
# service agent into a table it creates in `agent_logs`. A dataset of its own, so the service agent's write reaches
# nothing else; free while it stays inside BigQuery's 10 GiB (a 60-day table expiry bounds it), and only while
# the data agent's API is on the free path (free-path.yaml, until #232 switches it off). `make gcp-data-agent`
# points the agent at it (platform/gcp/data-agent/publish.py, AGENT_LOGS_TABLE).

locals {
  data_agent_on = lookup(local.free_path.apis, "geminidataanalytics.googleapis.com", { enable = false }).enable
}

data "google_project" "lab" {
  project_id = var.project
}

resource "google_bigquery_dataset" "agent_logs" {
  count = local.data_agent_on ? 1 : 0

  dataset_id                  = "agent_logs"
  location                    = "US"
  description                 = "The data agent's conversation logs (BigQuery Agent Analytics, #207), written by Google's Gemini Data Analytics service agent."
  default_table_expiration_ms = 60 * 24 * 3600 * 1000
  labels                      = { layer = "agent-logs" }
  delete_contents_on_destroy  = true

  depends_on = [google_project_service.free_path]
}

# The service agent Google creates when the API is enabled writes the log table; it needs no other grant.
resource "google_bigquery_dataset_iam_member" "agent_logs_writer" {
  count = local.data_agent_on ? 1 : 0

  dataset_id = google_bigquery_dataset.agent_logs[0].dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:service-${data.google_project.lab.number}@gcp-sa-geminidataanalytics.iam.gserviceaccount.com"
}
