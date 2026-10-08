# IAP authenticates every ingress path, including the default run.app URL.
# https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run
resource "google_cloud_run_v2_service" "litellm" {
  count                = local.runtime_enabled ? 1 : 0
  project              = var.project_id
  location             = var.region
  name                 = "litellm"
  deletion_protection  = true
  ingress              = "INGRESS_TRAFFIC_ALL"
  iap_enabled          = true
  invoker_iam_disabled = false
  labels               = { application = "litellm", environment = "preprod" }

  template {
    service_account                  = google_service_account.runtime.email
    timeout                          = "600s"
    max_instance_request_concurrency = 20
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    containers {
      image = local.proxy_image
      args  = local.proxy_args
      ports {
        container_port = 4000
      }
      resources {
        # Pin Cloud Run defaults to reset existing revisions as well.
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = false
        startup_cpu_boost = true
      }
      dynamic "env" {
        for_each = merge(local.proxy_env, local.redis_env, { ROOT_REDIRECT_URL = "/ui", PROXY_BASE_URL = local.base_url })
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = merge(local.proxy_secret_env, local.proxy_provider_secret_env, local.redis_secret_env)
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
      volume_mounts {
        name       = "config"
        mount_path = "/etc/litellm"
      }
      dynamic "volume_mounts" {
        for_each = local.redis_ca_enabled ? [1] : []
        content {
          name       = "redis-ca"
          mount_path = "/etc/redis"
        }
      }
      dynamic "volume_mounts" {
        for_each = local.proxy_database_ca_enabled ? [1] : []
        content {
          name       = "database-ca"
          mount_path = "/etc/database"
        }
      }
      dynamic "startup_probe" {
        for_each = [local.proxy_probes.startup]
        content {
          http_get {
            path = startup_probe.value.path
            port = 4000
          }
          period_seconds    = startup_probe.value.period_seconds
          timeout_seconds   = startup_probe.value.timeout_seconds
          failure_threshold = startup_probe.value.failure_threshold
        }
      }
      dynamic "liveness_probe" {
        for_each = [local.proxy_probes.liveness]
        content {
          http_get {
            path = liveness_probe.value.path
            port = 4000
          }
          period_seconds    = liveness_probe.value.period_seconds
          timeout_seconds   = liveness_probe.value.timeout_seconds
          failure_threshold = liveness_probe.value.failure_threshold
        }
      }
    }
    dynamic "volumes" {
      for_each = local.redis_ca_enabled ? [1] : []
      content {
        name = "redis-ca"
        secret {
          secret = google_secret_manager_secret.redis["ca"].secret_id
          items {
            version = var.redis_connection.ca_version
            path    = "ca.pem"
          }
        }
      }
    }
    volumes {
      name = "config"
      secret {
        secret = google_secret_manager_secret.config.secret_id
        items {
          version = google_secret_manager_secret_version.config.version
          path    = "config.yaml"
        }
      }
    }
    dynamic "volumes" {
      for_each = local.proxy_database_ca_enabled ? [1] : []
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
  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
  depends_on = [
    google_project_service_identity.iap,
    google_project_iam_member.vertex,
    google_secret_manager_secret_iam_member.runtime,
    google_secret_manager_secret_iam_member.config,
    google_secret_manager_secret_iam_member.provider,
    google_secret_manager_secret_iam_member.redis,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  count    = local.runtime_enabled ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.litellm[0].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_project_service_identity.iap.email}"
}

resource "google_iap_web_cloud_run_service_iam_member" "users" {
  for_each               = local.runtime_enabled ? var.iap_members : toset([])
  project                = var.project_id
  location               = var.region
  cloud_run_service_name = google_cloud_run_v2_service.litellm[0].name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = each.value
}
