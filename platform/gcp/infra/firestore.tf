# The agent's ADK sessions (SL-13; used from #209): Firestore's one free database per project, the
# `(default)` Standard edition database, at 1 GiB stored and 50,000 reads and 20,000 writes a day.
# TTL deletes, point-in-time recovery, backups, restores and clones have no free usage: none is turned on.

resource "google_firestore_database" "sessions" {
  name                              = "(default)"
  location_id                       = var.region
  type                              = "FIRESTORE_NATIVE"
  database_edition                  = "STANDARD"
  point_in_time_recovery_enablement = "POINT_IN_TIME_RECOVERY_DISABLED"
  delete_protection_state           = "DELETE_PROTECTION_DISABLED"
  # `make gcp-down` removes it; the provider's default would only forget it.
  deletion_policy = "DELETE"

  depends_on = [google_project_service.free_path]
}
