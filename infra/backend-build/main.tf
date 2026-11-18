terraform {
  required_version = ">= 1.9, < 2.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
  backend "gcs" {}
}

locals {
  project_id = "preprod-deep-copy"
  region     = "europe-west1"
  # Repositories that receive backend images. Owned by infra/bootstrap and infra/momentum.
  repositories = toset(["market-scanner", "momentum"])
}

provider "google" {
  project = local.project_id
  region  = local.region
}

# Replaces the default compute identity (roles/editor) for backend image builds.
resource "google_service_account" "builder" {
  project      = local.project_id
  account_id   = "backend-builder"
  display_name = "Build backend images only"
}

resource "google_storage_bucket" "sources" {
  project                     = local.project_id
  name                        = "${local.project_id}-backend-build-sources"
  location                    = local.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  lifecycle_rule {
    condition {
      age = 7
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket_iam_member" "source_reader" {
  bucket = google_storage_bucket.sources.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_artifact_registry_repository_iam_member" "publisher" {
  for_each   = local.repositories
  project    = local.project_id
  location   = local.region
  repository = each.value
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_project_iam_member" "build_logs" {
  project = local.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.builder.email}"
}

output "build_service_account" {
  value = google_service_account.builder.name
}

output "source_staging_directory" {
  value = "gs://${google_storage_bucket.sources.name}/source"
}
