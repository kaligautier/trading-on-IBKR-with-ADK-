terraform {
  required_version = ">= 1.9, < 2.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.46"
    }
  }
  backend "gcs" {}
}
provider "google" {
  project = var.project_id
  region  = var.region
}
resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "momentum"
  format        = "DOCKER"
}
resource "google_service_account" "worker" {
  project      = var.project_id
  account_id   = "momentum-worker"
  display_name = "Momentum private analysis worker"
}
resource "google_secret_manager_secret" "database" {
  for_each  = toset(["momentum-session-database-url", "momentum-result-database-url"])
  project   = var.project_id
  secret_id = each.key
  replication {
    auto {}
  }
}
resource "google_secret_manager_secret_iam_member" "database" {
  for_each  = google_secret_manager_secret.database
  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}
resource "google_secret_manager_secret_iam_member" "llm" {
  project   = var.project_id
  secret_id = "litellm-client-momentum"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}
resource "google_cloud_run_v2_job" "analysis" {
  count               = var.image == "" ? 0 : 1
  project             = var.project_id
  location            = var.region
  name                = "momentum-analysis"
  deletion_protection = true
  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.worker.email
      timeout         = "1800s"
      max_retries     = 0
      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = "private-services"
          subnetwork = "cloud-run-egress"
        }
      }
      containers {
        image = var.image
        resources { limits = { cpu = "1", memory = "2Gi" } }
        dynamic "env" {
          for_each = {
            LITELLM_API_BASE     = var.gateway_url
            MOMENTUM_QUICK_MODEL = var.model
            MOMENTUM_DEEP_MODEL  = var.model
          }
          content {
            name  = env.key
            value = env.value
          }
        }
        dynamic "env" {
          for_each = {
            LITELLM_API_KEY               = { secret = "litellm-client-momentum", version = var.llm_key_version }
            MOMENTUM_SESSION_DATABASE_URL = { secret = "momentum-session-database-url", version = var.session_database_version }
            MOMENTUM_RESULT_DATABASE_URL  = { secret = "momentum-result-database-url", version = var.result_database_version }
          }
          content {
            name = env.key
            value_source {
              secret_key_ref {
                secret  = env.value.secret
                version = env.value.version
              }
            }
          }
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.database, google_secret_manager_secret_iam_member.llm]
}
output "job_name" { value = try(google_cloud_run_v2_job.analysis[0].name, null) }
output "worker_identity" { value = google_service_account.worker.email }
output "image_repository" { value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}/worker" }
