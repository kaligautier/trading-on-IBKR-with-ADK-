# Execute this job successfully before enabling the service or upgrading its image.
# https://docs.litellm.ai/docs/proxy/deploy
resource "google_cloud_run_v2_job" "migrations" {
  count               = local.jobs_enabled ? 1 : 0
  project             = var.project_id
  location            = var.region
  name                = "litellm-migrations"
  deletion_protection = true
  template {
    task_count  = 1
    parallelism = 1
    template {
      service_account = google_service_account.migrations.email
      timeout         = "1200s"
      max_retries     = 0
      containers {
        image = local.migration_image
        resources {
          limits = { cpu = "1", memory = "1Gi" }
        }
        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.credentials["database-url"].secret_id
              version = lookup(var.secret_versions, "database-url", "1")
            }
          }
        }
        dynamic "volume_mounts" {
          for_each = contains(keys(var.secret_versions), "database-ca") ? [1] : []
          content {
            name       = "database-ca"
            mount_path = "/etc/database"
          }
        }
      }
      dynamic "volumes" {
        for_each = contains(keys(var.secret_versions), "database-ca") ? [1] : []
        content {
          name = "database-ca"
          secret {
            secret = google_secret_manager_secret.credentials["database-ca"].secret_id
            items {
              version = var.secret_versions["database-ca"]
              path    = "ca.pem"
            }
          }
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.migrations]
}
