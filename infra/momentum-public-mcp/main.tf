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
  for_each = toset(["momentum-api", "market-scanner-api"])
  project  = var.project_id
  location = var.region
  name     = each.key
}

resource "google_service_account" "mcp" {
  project      = var.project_id
  account_id   = "momentum-public-mcp"
  display_name = "Public MCP: invoke private consultation APIs only"
}

resource "google_cloud_run_v2_service_iam_member" "reader" {
  for_each = data.google_cloud_run_v2_service.reader
  project  = var.project_id
  location = var.region
  name     = each.value.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.mcp.email}"
}

resource "google_secret_manager_secret_iam_member" "caller_key" {
  project   = var.project_id
  secret_id = var.caller_key_resource
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.mcp.email}"
}

resource "google_cloud_run_v2_service" "mcp" {
  project              = var.project_id
  name                 = "momentum-public-mcp"
  location             = var.region
  deletion_protection  = true
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = true
  labels               = { application = "momentum", component = "public-mcp" }
  template {
    service_account                  = google_service_account.mcp.email
    timeout                          = "60s"
    max_instance_request_concurrency = 20
    session_affinity                 = false
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
    containers {
      image = var.image
      ports { container_port = 8080 }
      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      dynamic "env" {
        for_each = {
          MOMENTUM_API_URL        = data.google_cloud_run_v2_service.reader["momentum-api"].uri
          MARKET_SCANNER_API_URL  = data.google_cloud_run_v2_service.reader["market-scanner-api"].uri
          MOMENTUM_API_USE_IAM    = "true"
          GOOGLE_CLOUD_PROJECT    = var.project_id
          LOG_SUCCESS_SAMPLE_RATE = tostring(var.log_success_sample_rate)
          LOG_SLOW_REQUEST_MS     = tostring(var.log_slow_request_ms)
          TRUSTED_PROXIES         = var.trusted_proxies
        }
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "SUGGESTION_HASH_SECRET"
        value_source {
          secret_key_ref {
            secret  = var.caller_key_resource
            version = var.caller_key_version
          }
        }
      }
      startup_probe {
        http_get { path = "/health" }
        period_seconds    = 5
        failure_threshold = 12
      }
      liveness_probe {
        http_get { path = "/health" }
        period_seconds = 30
      }
    }
  }
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  depends_on = [google_cloud_run_v2_service_iam_member.reader, google_secret_manager_secret_iam_member.caller_key]
}

output "service_url" { value = google_cloud_run_v2_service.mcp.uri }
output "service_account" { value = google_service_account.mcp.email }
