# The lab project's one OpenTofu root (semantic/PLAN.md SL-13): every GCP resource, validated offline by
# `make gcp-validate`, planned by `make gcp-plan`, applied by the project's owner with `make gcp-up`.
terraform {
  required_version = "~> 1.10.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.9.0"
    }
  }

  # State in the project's own bucket (Cloud Storage's free 5 GB in us-central1), named by
  # `make gcp-plan` / `gcp-up` as `<project>-tfstate`; `make gcp-validate` runs without a backend.
  # No prefix: the object is `default.tfstate`, a name without a slash, because the cloud sessions'
  # egress proxy decodes the `%2F` the storage JSON API needs, and a slashed name reads as 404 there.
  backend "gcs" {}
}

provider "google" {
  project = var.project
  region  = var.region

  default_labels = {
    lab = "pplk8s"
  }
}
