data "google_project" "current" {
  project_id = var.project_id
}

locals {
  # https://docs.cloud.google.com/run/docs/triggering/https-request#deterministic
  base_url        = "https://litellm-${data.google_project.current.number}.${var.region}.run.app"
  gateway_url     = "https://litellm-gateway-${data.google_project.current.number}.${var.region}.run.app"
  runtime_enabled = var.stage == "service"
  jobs_enabled    = var.stage != "foundation"
  secret_names    = toset(["database-url", "master-key", "salt-key", "ui-password", "database-ca"])
  image_prefix    = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.litellm.repository_id}/berriai"
  proxy_image     = "${local.image_prefix}/litellm@${var.proxy_digest}"
  migration_image = "${local.image_prefix}/litellm-migrations@${var.migrations_digest}"
  runtime_secrets = {
    DATABASE_URL       = "database-url"
    LITELLM_MASTER_KEY = "master-key"
    LITELLM_SALT_KEY   = "salt-key"
    UI_PASSWORD        = "ui-password" # gitleaks:allow -- Secret Manager ID, not a password.
  }
  # Official configuration: https://docs.litellm.ai/docs/proxy/config_settings
  runtime_settings = jsondecode(file("${path.module}/config/runtime-settings.json"))
  proxy_config = yamlencode({
    model_list = concat([{
      model_name = var.model
      litellm_params = {
        model           = "vertex_ai/${var.model}"
        vertex_project  = var.project_id
        vertex_location = var.vertex_location
      }
      }], [for model in sort(tolist(var.additional_vertex_models)) : {
      model_name = model
      litellm_params = {
        model           = "vertex_ai/${model}"
        vertex_project  = var.project_id
        vertex_location = var.vertex_location
      }
    }], local.provider_models)
    general_settings = merge(local.runtime_settings.general_settings, {
      master_key                       = "os.environ/LITELLM_MASTER_KEY"
      database_url                     = "os.environ/DATABASE_URL"
      database_connection_pool_limit   = 2
      allow_requests_on_db_unavailable = false
      store_model_in_db                = true
    })
    litellm_settings = local.runtime_settings.litellm_settings
    router_settings  = local.runtime_settings.router_settings
  })
}

# Shared APIs, state bucket and scanner resources remain owned by infra/bootstrap.
resource "google_project_service" "iap" {
  project            = var.project_id
  service            = "iap.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service_identity" "iap" {
  provider = google-beta
  project  = var.project_id
  service  = google_project_service.iap.service
}

# Cloud Run cannot pull GHCR URLs directly. Use its documented AR remote path.
# https://berriai.github.io/litellm/terraform/litellm/gcp/#image-pulls
resource "google_artifact_registry_repository" "litellm" {
  project       = var.project_id
  location      = var.region
  repository_id = "litellm"
  format        = "DOCKER"
  mode          = "REMOTE_REPOSITORY"
  remote_repository_config {
    description = "Official LiteLLM images from GHCR"
    docker_repository {
      custom_repository {
        uri = "https://ghcr.io"
      }
    }
  }
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "litellm"
  display_name = "LiteLLM runtime"
}

resource "google_service_account" "migrations" {
  project      = var.project_id
  account_id   = "litellm-migrations"
  display_name = "LiteLLM database migrations"
}

resource "google_project_iam_member" "vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret" "credentials" {
  for_each            = local.secret_names
  project             = var.project_id
  secret_id           = "litellm-${each.key}"
  version_destroy_ttl = "2592000s"
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_iam_member" "runtime" {
  for_each  = local.secret_names
  project   = var.project_id
  secret_id = google_secret_manager_secret.credentials[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "migrations" {
  for_each  = toset(["database-url", "database-ca"])
  project   = var.project_id
  secret_id = google_secret_manager_secret.credentials[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.migrations.email}"
}

# This payload contains configuration only, never credentials.
resource "google_secret_manager_secret" "config" {
  project             = var.project_id
  secret_id           = "litellm-config"
  version_destroy_ttl = "2592000s"
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_version" "config" {
  secret          = google_secret_manager_secret.config.id
  secret_data     = local.proxy_config
  deletion_policy = "ABANDON"
  lifecycle {
    create_before_destroy = true
  }
}

resource "google_secret_manager_secret_iam_member" "config" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.config.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}
