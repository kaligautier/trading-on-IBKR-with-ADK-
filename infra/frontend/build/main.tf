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

provider "google" {
  project = "preprod-deep-copy"
  region  = "europe-west1"
}

resource "google_project_service" "cloud_build" {
  project            = "preprod-deep-copy"
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

resource "google_service_account" "builder" {
  project      = "preprod-deep-copy"
  account_id   = "deepcopy-front-builder"
  display_name = "Build DeepCopy frontend images only"
}

resource "google_storage_bucket" "sources" {
  project                     = "preprod-deep-copy"
  name                        = "preprod-deep-copy-front-build-sources"
  location                    = "europe-west1"
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
  project    = "preprod-deep-copy"
  location   = "europe-west1"
  repository = "market-scanner"
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_project_iam_member" "build_logs" {
  project = "preprod-deep-copy"
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.builder.email}"
}

output "build_service_account" {
  value = google_service_account.builder.name
}

output "source_staging_directory" {
  value = "gs://${google_storage_bucket.sources.name}/source"
}
