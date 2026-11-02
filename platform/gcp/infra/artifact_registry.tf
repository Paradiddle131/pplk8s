# Artifact Registry (#230): the one Docker repository Cloud Run pulls the lab's images from (#209, #227).
# Storage is free up to 0.5 GiB-month per billing account, billed by the hour past it; pulls by Cloud Run in
# us-central1 are free, pulls to anything outside Google Cloud are internet egress (platform/gcp/README.md).
# Each image keeps its two newest versions (the deployed tag and the one before it) and the cleanup policy
# deletes the rest; vulnerability scanning stays off, because it bills per image scanned.

resource "google_artifact_registry_repository" "images" {
  repository_id = "pplk8s"
  location      = var.region
  format        = "DOCKER"
  description   = "The lab's workload images (EL Factory, dbt, semantic agent), two versions each."

  docker_config {
    # Tags stay mutable: in a repository with immutable tags, tagged versions cannot be deleted, not even by the
    # cleanup policies below, so the registry would only grow (seen 2026-11-02: every delete FAILED_PRECONDITION;
    # https://docs.cloud.google.com/artifact-registry/docs/repositories/cleanup-policy). A tag still names one build
    # (PLAN.md D16): tags are computed from the image's content, and `make gcp-images` never pushes over a tag the
    # registry already holds.
    immutable_tags = false
  }

  vulnerability_scanning_config {
    enablement_config = "DISABLED"
  }

  cleanup_policy_dry_run = false

  # KEEP wins over DELETE: every version goes except each package's two newest.
  cleanup_policies {
    id     = "delete-all"
    action = "DELETE"
    condition {
      tag_state = "ANY"
    }
  }

  cleanup_policies {
    id     = "keep-two-newest"
    action = "KEEP"
    most_recent_versions {
      keep_count = 2
    }
  }

  depends_on = [google_project_service.free_path]
}

# The cloud sessions' credential pushes the images and reads the repository's size; it holds no other
# Artifact Registry role, and none on any other repository.
resource "google_artifact_registry_repository_iam_member" "automation_writer" {
  location   = google_artifact_registry_repository.images.location
  repository = google_artifact_registry_repository.images.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:pplk8s-automation@${var.project}.iam.gserviceaccount.com"
}

output "image_registry" {
  description = "Where the lab's images go on GCP: <region>-docker.pkg.dev/<project>/pplk8s."
  value       = "${var.region}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.images.repository_id}"
}
