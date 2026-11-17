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

resource "google_service_account" "builder" {
  project      = "preprod-deep-copy"
  account_id   = "momentum-mcp-builder"
  display_name = "Build Momentum public MCP images only"
}

resource "google_storage_bucket" "sources" {
  project                     = "preprod-deep-copy"
  name                        = "preprod-deep-copy-mcp-build-sources"
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

resource "google_secret_manager_secret" "caller_key" {
  project             = "preprod-deep-copy"
  secret_id           = "momentum-mcp-caller-key"
  deletion_protection = true
  replication {
    auto {}
  }
}
