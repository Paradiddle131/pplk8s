# The APIs on the free path that are turned on now: free-path.yaml is the one list, and
# check_free_path.py keeps it free of paid services.
locals {
  free_path = yamldecode(file("${path.module}/../free-path.yaml"))
  apis      = toset([for name, api in local.free_path.apis : name if api.enable])
}

resource "google_project_service" "free_path" {
  for_each = local.apis

  service = each.value
  # Turning an API off on destroy can break the owner's other work in the project; gcp-down leaves them on.
  disable_on_destroy         = false
  disable_dependent_services = false
}
