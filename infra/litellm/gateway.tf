# Private inference gateway: same image, config and database as the IAP-protected
# admin service, but internal-only ingress and no IAP. Only VPC-attached clients
# (the scanner's Direct VPC egress) can reach it.
# https://docs.cloud.google.com/run/docs/securing/private-networking

resource "google_project_service" "compute" {
  project            = var.project_id
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "dns" {
  project            = var.project_id
  service            = "dns.googleapis.com"
  disable_on_destroy = false
}

resource "google_compute_network" "private" {
  project                 = var.project_id
  name                    = "private-services"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.compute]
}

resource "google_compute_subnetwork" "run" {
  project                  = var.project_id
  region                   = var.region
  name                     = "cloud-run-egress"
  network                  = google_compute_network.private.id
  ip_cidr_range            = "10.8.0.0/26"
  private_ip_google_access = true
}

# Resolve *.run.app to the private.googleapis.com VIPs so calls enter Cloud Run as VPC traffic.
resource "google_dns_managed_zone" "run_app" {
  project    = var.project_id
  name       = "run-app-private"
  dns_name   = "run.app."
  visibility = "private"
  private_visibility_config {
    networks {
      network_url = google_compute_network.private.id
    }
  }
  depends_on = [google_project_service.dns]
}

resource "google_dns_record_set" "run_app" {
  project      = var.project_id
  managed_zone = google_dns_managed_zone.run_app.name
  name         = "*.run.app."
  type         = "A"
  ttl          = 300
  rrdatas      = ["199.36.153.8", "199.36.153.9", "199.36.153.10", "199.36.153.11"]
}

resource "google_cloud_run_v2_service" "gateway" {
  count               = local.runtime_enabled ? 1 : 0
  project             = var.project_id
  location            = var.region
  name                = "litellm-gateway"
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  iap_enabled         = false
  # Reachable only from the VPC; callers authenticate with their LiteLLM virtual key.
  invoker_iam_disabled = true
  labels               = { application = "litellm-gateway", environment = "preprod" }

  template {
    service_account                  = google_service_account.runtime.email
    timeout                          = "600s"
    max_instance_request_concurrency = 20
    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }
    # Keep ingress first: the provider preserves computed ports by container index.
    # Only this container receives Cloud Run ingress. The proxy is reachable on localhost.
    containers {
      name       = "routes"
      image      = local.gateway_filter_image
      command    = ["nginx"]
      args       = ["-c", "/etc/gateway/nginx.conf", "-g", "daemon off;"]
      depends_on = ["proxy"]
      ports { container_port = 4000 }
      resources {
        # Pin Cloud Run defaults to reset existing revisions as well.
        limits   = { cpu = "1", memory = "512Mi" }
        cpu_idle = true
      }
      volume_mounts {
        name       = "gateway-routes"
        mount_path = "/etc/gateway"
      }
      startup_probe {
        http_get {
          path = "/health/readiness"
          port = 4000
        }
        period_seconds    = 10
        timeout_seconds   = 5
        failure_threshold = 24
      }
    }
    containers {
      name  = "proxy"
      image = local.proxy_image
      args  = ["--config", "/etc/litellm/config.yaml", "--port", "4001", "--num_workers", "1"]
      resources {
        limits            = { cpu = "1", memory = "512Mi" }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      dynamic "env" {
        for_each = merge({ for key, value in local.proxy_env : key => value if key != "UI_USERNAME" }, local.redis_env, {
          DISABLE_ADMIN_UI = "true", PROXY_BASE_URL = local.gateway_url
        })
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = merge({ for key, value in local.proxy_secret_env : key => value if key != "UI_PASSWORD" }, local.proxy_provider_secret_env, local.redis_secret_env)
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
            port = 4001
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
            port = 4001
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
      name = "gateway-routes"
      secret {
        secret = google_secret_manager_secret.gateway_routes.secret_id
        items {
          version = google_secret_manager_secret_version.gateway_routes.version
          path    = "nginx.conf"
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
    google_project_iam_member.vertex,
    google_secret_manager_secret_iam_member.runtime,
    google_secret_manager_secret_iam_member.config,
    google_secret_manager_secret_iam_member.provider,
    google_secret_manager_secret_iam_member.gateway_routes,
    google_secret_manager_secret_iam_member.redis,
  ]
}
