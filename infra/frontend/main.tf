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
  project = var.project_id
  region  = var.region
}

data "google_cloud_run_v2_service" "reader" {
  project  = var.project_id
  location = var.region
  name     = "market-scanner-api"
}

resource "google_service_account" "frontend" {
  project      = var.project_id
  account_id   = "market-scanner-front"
  display_name = "Public Market Scanner frontend"
}

resource "google_cloud_run_v2_service_iam_member" "reader_invoker" {
  project  = var.project_id
  location = var.region
  name     = data.google_cloud_run_v2_service.reader.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.frontend.email}"
}

resource "google_cloud_run_v2_service" "frontend" {
  project              = var.project_id
  name                 = "market-scanner-front"
  location             = var.region
  deletion_protection  = true
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = true
  labels               = { application = "market-scanner", component = "frontend" }

  template {
    service_account                  = google_service_account.frontend.email
    timeout                          = "30s"
    max_instance_request_concurrency = 20
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      image = var.image
      ports {
        container_port = 3000
      }
      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      env {
        name  = "MARKET_SCANNER_API_URL"
        value = data.google_cloud_run_v2_service.reader.uri
      }
      env {
        name  = "MARKET_SCANNER_API_USE_IAM"
        value = "true"
      }
      startup_probe {
        http_get {
          path = "/health"
          port = 3000
        }
        period_seconds    = 5
        timeout_seconds   = 2
        failure_threshold = 12
      }
      liveness_probe {
        http_get {
          path = "/health"
          port = 3000
        }
        period_seconds = 30
      }
    }
  }
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  depends_on = [google_cloud_run_v2_service_iam_member.reader_invoker]
}

output "service_url" {
  value = google_cloud_run_v2_service.frontend.uri
}
