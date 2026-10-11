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

resource "google_service_account" "reader" {
  project      = var.project_id
  account_id   = "market-scanner-api"
  display_name = "Market Scanner read-only consultation"
}

resource "google_secret_manager_secret_iam_member" "reader" {
  for_each  = toset([var.database_secret_id, var.ca_secret_id])
  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.reader.email}"
}

resource "google_cloud_run_v2_service" "reader" {
  project              = var.project_id
  name                 = "market-scanner-api"
  location             = var.region
  deletion_protection  = true
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false
  labels               = { application = "market-scanner", component = "reader" }

  template {
    service_account                  = google_service_account.reader.email
    timeout                          = "30s"
    max_instance_request_concurrency = 20
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      image = var.image
      ports {
        container_port = 8080
      }
      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      dynamic "env" {
        for_each = {
          AUTH_MODE             = "cloud_run"
          DATABASE_SCHEMA       = "market_scanner"
          DATABASE_POOL_SIZE    = "1"
          DATABASE_POOL_TIMEOUT = "5"
        }
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = var.database_secret_id
            version = var.database_secret_version
          }
        }
      }
      volume_mounts {
        name       = "database-ca"
        mount_path = "/etc/database"
      }
      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        period_seconds    = 5
        timeout_seconds   = 2
        failure_threshold = 12
      }
      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        period_seconds = 30
      }
    }
    volumes {
      name = "database-ca"
      secret {
        secret = var.ca_secret_id
        items {
          version = var.ca_secret_version
          path    = "ca.pem"
        }
      }
    }
  }
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  depends_on = [google_secret_manager_secret_iam_member.reader]
}

resource "google_cloud_run_v2_service_iam_member" "invoker" {
  for_each = var.invoker_members
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.reader.name
  role     = "roles/run.invoker"
  member   = each.value
}

output "service_url" {
  value = google_cloud_run_v2_service.reader.uri
}
