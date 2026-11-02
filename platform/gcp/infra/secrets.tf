# The agent's model key (OPENROUTER_API_KEY) in Secret Manager (#209): free up to 6 active secret versions
# and 10,000 access operations a month per billing account; one replica in us-central1, so one active version
# is one billed location. OpenTofu declares the secret only: the owner adds its version by hand
# (platform/gcp/README.md), so the key never enters the state. The agent reads it once per instance start.

resource "google_secret_manager_secret" "openrouter_key" {
  secret_id = "openrouter-api-key"

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.free_path]
}

# The agent's account reads this one secret, and no other.
resource "google_secret_manager_secret_iam_member" "agent_key" {
  secret_id = google_secret_manager_secret.openrouter_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.workload["semantic-agent"].email}"
}
