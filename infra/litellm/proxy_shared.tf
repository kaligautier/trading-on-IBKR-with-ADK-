# Container settings shared by the IAP-protected admin service (service.tf) and
# the private inference gateway (gateway.tf). Only exposure, scaling and URLs
# differ between them; keep everything else here so the two cannot drift.
locals {
  proxy_args = ["--config", "/etc/litellm/config.yaml", "--port", "4000", "--num_workers", "1"]

  # Documented production settings: https://docs.litellm.ai/docs/proxy/prod
  proxy_env = {
    DISABLE_SCHEMA_UPDATE = "true"
    STORE_MODEL_IN_DB     = "True"
    UI_USERNAME           = "admin"
    DOCS_URL              = "/docs"
    LITELLM_LOG           = "INFO"
    LITELLM_MODE          = "PRODUCTION"
    GOOGLE_CLOUD_PROJECT  = var.project_id
    VERTEXAI_PROJECT      = var.project_id
    VERTEXAI_LOCATION     = var.vertex_location
  }

  proxy_secret_env = {
    for name, secret in local.runtime_secrets : name => {
      secret  = google_secret_manager_secret.credentials[secret].secret_id
      version = lookup(var.secret_versions, secret, "1")
    }
  }
  proxy_provider_secret_env = {
    for provider, version in var.provider_secret_versions : local.provider_environment[provider] => {
      secret  = google_secret_manager_secret.provider[provider].secret_id
      version = version
    }
  }

  proxy_database_ca_enabled = contains(keys(var.secret_versions), "database-ca")

  proxy_probes = {
    startup = {
      path              = "/health/readiness"
      period_seconds    = 10
      timeout_seconds   = 5
      failure_threshold = 24
    }
    liveness = {
      path              = "/health/liveliness"
      period_seconds    = 30
      timeout_seconds   = 5
      failure_threshold = 3
    }
  }
}
