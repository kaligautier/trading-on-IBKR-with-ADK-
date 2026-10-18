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

# The shared registry, APIs and state bucket belong to infra/bootstrap.
data "google_cloud_run_v2_service" "reader" {
  project  = var.project_id
  location = var.region
  name     = "market-scanner-api"
}

resource "google_service_account" "frontend" {
  project      = var.project_id
  account_id   = "deepcopy-front"
  display_name = "DeepCopy public frontend"
}

# Additive grant: do not take ownership of the reader's other callers.
resource "google_cloud_run_v2_service_iam_member" "reader_invoker" {
  project  = var.project_id
  location = var.region
  name     = data.google_cloud_run_v2_service.reader.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.frontend.email}"
}

resource "google_cloud_run_v2_service" "frontend" {
  project              = var.project_id
  name                 = "deepcopy-front"
  location             = var.region
  deletion_protection  = true
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = true
  labels               = { application = "market-scanner", component = "frontend" }

  template {
    service_account                  = google_service_account.frontend.email
    timeout                          = "60s"
    max_instance_request_concurrency = 20
    scaling {
      min_instance_count = 0
      max_instance_count = 3
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
        failure_threshold = 24
      }
    }
  }
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  depends_on = [google_cloud_run_v2_service_iam_member.reader_invoker]
}

# A second, explicit plan transfers the existing domains from Demo ADK.
resource "google_cloud_run_domain_mapping" "frontend" {
  for_each = var.enable_domain_mappings ? toset(["deepcopy.fr", "www.deepcopy.fr"]) : toset([])
  project  = var.project_id
  location = var.region
  name     = each.value
  metadata {
    namespace = var.project_id
  }
  spec {
    route_name     = google_cloud_run_v2_service.frontend.name
    force_override = true
  }
  lifecycle {
    prevent_destroy = true
  }
}

output "service_url" {
  value = google_cloud_run_v2_service.frontend.uri
}

output "service_account_email" {
  value = google_service_account.frontend.email
}

output "domain_resource_records" {
  description = "Compare Google's required records with the existing Squarespace DNS after cutover."
  value       = { for domain, mapping in google_cloud_run_domain_mapping.frontend : domain => mapping.status[0].resource_records }
}
