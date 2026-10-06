# Provider values never enter Terraform. Cloud Run resolves numeric secret versions.
locals {
  provider_environment = {
    openai    = "OPENAI_API_KEY"
    anthropic = "ANTHROPIC_API_KEY"
    gemini    = "GEMINI_API_KEY"
  }
  provider_models = [for alias, model in var.provider_models : {
    model_name = alias
    litellm_params = {
      model   = "${model.provider}/${model.model}"
      api_key = "os.environ/${lookup(local.provider_environment, model.provider, "INVALID_PROVIDER")}"
    }
  }]
}

variable "provider_secret_versions" {
  description = "Enable an API-key provider by pinning an uploaded Secret Manager version. Never put key values here."
  type        = map(string)
  default     = {}
  validation {
    condition = alltrue([for provider, version in var.provider_secret_versions :
      contains(["openai", "anthropic", "gemini"], provider) && can(regex("^[1-9][0-9]*$", version))
    ])
    error_message = "Use openai, anthropic or gemini with positive numeric secret versions."
  }
}

variable "provider_models" {
  description = "Explicit public aliases mapped to provider model IDs without the provider prefix."
  type = map(object({
    provider = string
    model    = string
  }))
  default = {}
  validation {
    condition = alltrue([for alias, model in var.provider_models :
      can(regex("^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$", alias)) && alias != var.model && !contains(var.additional_vertex_models, alias) &&
      contains(["openai", "anthropic", "gemini"], model.provider) &&
      contains(keys(var.provider_secret_versions), model.provider) &&
      can(regex("^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,199}$", model.model))
    ])
    error_message = "Use unique explicit aliases, a supported provider with a pinned secret version, and a model ID without wildcards, URLs or provider prefixes."
  }
}

# Empty containers are safe to prepare before provider credentials are available.
resource "google_secret_manager_secret" "provider" {
  for_each            = local.provider_environment
  project             = var.project_id
  secret_id           = "litellm-provider-${each.key}"
  version_destroy_ttl = "2592000s"
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_iam_member" "provider" {
  for_each  = var.provider_secret_versions
  project   = var.project_id
  secret_id = google_secret_manager_secret.provider[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}
