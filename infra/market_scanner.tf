locals {
  scanner_gateway = [var.litellm_gateway]
  scanner_environment = {
    DOCKER_ENV                           = "true"
    DEBUG                                = "false"
    LOG_LEVEL                            = "INFO"
    GOOGLE_GENAI_USE_VERTEXAI            = "false"
    GOOGLE_GENAI_USE_ENTERPRISE          = "false"
    GOOGLE_CLOUD_PROJECT                 = var.project_id
    GOOGLE_CLOUD_LOCATION                = var.vertex_location
    MARKET_SCANNER_GOOGLE_CLOUD_LOCATION = var.vertex_location
    MARKET_SCANNER_MODEL                 = var.model
    ADK_ALLOW_ORIGINS                    = jsonencode(["http://127.0.0.1:8080"])
    DATABASE_SCHEMA                      = var.database_schema
    DATABASE_POOL_SIZE                   = "1"
    DATABASE_POOL_TIMEOUT                = "30"
    DD_TRACE_ENABLED                     = "false"
    DD_INSTRUMENTATION_TELEMETRY_ENABLED = "false"
    LITELLM_API_BASE                     = var.litellm_gateway.url
  }
}

resource "google_cloud_run_v2_service" "scanner" {
  project              = var.project_id
  name                 = "market-scanner-adk"
  location             = var.region
  deletion_protection  = true
  ingress              = "INGRESS_TRAFFIC_ALL"
  invoker_iam_disabled = false

  labels = { application = "market-scanner", component = "backend" }

  template {
    service_account                  = google_service_account.scanner.email
    timeout                          = "900s"
    max_instance_request_concurrency = 1

    dynamic "vpc_access" {
      for_each = local.scanner_gateway
      content {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = vpc_access.value.network
          subnetwork = vpc_access.value.subnetwork
        }
      }
    }

    # One writer connection per instance; allow capacity for revision overlap in DB.
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    containers {
      image = var.image
      # start_server.sh currently binds to 8000 regardless of PORT.
      ports {
        container_port = 8000
      }
      resources {
        limits            = { cpu = "1", memory = "1Gi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      dynamic "env" {
        for_each = local.scanner_environment
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = local.scanner_gateway
        content {
          name = "LITELLM_API_KEY"
          value_source {
            secret_key_ref {
              secret  = env.value.key_secret
              version = env.value.key_version
            }
          }
        }
      }
      env {
        name  = "MARKET_SCANNER_JOB"
        value = google_cloud_run_v2_job.daily_scan.id
      }
      env {
        name = "MARKET_SCANNER_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = "market-scanner-database-url"
            version = var.database_secret_version
          }
        }
      }
      startup_probe {
        http_get {
          path = "/health"
          port = 8000
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
  depends_on = [
    google_secret_manager_secret_iam_member.database,
    google_cloud_run_v2_job_iam_member.dispatcher,
  ]
}
