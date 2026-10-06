resource "google_cloud_run_v2_job" "daily_scan" {
  project             = var.project_id
  name                = "market-scanner-daily"
  location            = var.region
  deletion_protection = true

  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.scanner.email
      timeout         = "900s"
      max_retries     = 0
      containers {
        image   = var.image
        command = ["/app/.venv/bin/python"]
        args    = ["-m", "app.jobs.daily_scan"]
        resources {
          limits = { cpu = "1", memory = "1Gi" }
        }
        dynamic "env" {
          for_each = merge(local.scanner_environment, { PYTHONPATH = "/app/src" })
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
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.database, google_project_iam_member.vertex]
}

resource "google_cloud_run_v2_job_iam_member" "dispatcher" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.daily_scan.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scanner.email}"
}

output "daily_scan_job" {
  value = google_cloud_run_v2_job.daily_scan.id
}
