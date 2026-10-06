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
        for_each = {
          DOCKER_ENV                           = "true"
          DEBUG                                = "false"
          LOG_LEVEL                            = "INFO"
          GOOGLE_GENAI_USE_VERTEXAI            = "true"
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
        }
        content {
          name  = env.key
          value = env.value
        }
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
    google_project_iam_member.vertex,
  ]
}
