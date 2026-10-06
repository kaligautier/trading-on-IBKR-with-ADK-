terraform {
  required_version = ">= 1.9, < 2.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
  # First apply uses local state; migrate it with backend.remote.tf.example.
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "Existing GCP project with billing enabled."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Use a GCP project ID."
  }
}

variable "region" {
  type    = string
  default = "europe-west1"
}

resource "google_project_service" "apis" {
  for_each = toset([
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "terraform_state" {
  project                     = var.project_id
  name                        = "${var.project_id}-tfstate"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  versioning {
    enabled = true
  }
  soft_delete_policy {
    retention_duration_seconds = 604800
  }
  lifecycle {
    prevent_destroy = true
  }
  depends_on = [google_project_service.apis]
}

resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "market-scanner"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# Only metadata is managed here. Add the value outside Terraform/state.
resource "google_secret_manager_secret" "database" {
  project   = var.project_id
  secret_id = "market-scanner-database-url"
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
  depends_on = [google_project_service.apis]
}

output "state_bucket" {
  value = google_storage_bucket.terraform_state.name
}

output "image_repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
