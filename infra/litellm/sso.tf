# Google OAuth signs users into LiteLLM itself; IAP still gates every request.
# https://docs.litellm.ai/docs/proxy/admin_ui_sso
variable "google_sso" {
  description = "Optional Google SSO for the admin UI. Pin an uploaded client secret version and copy the administrator's User ID from LiteLLM after signing in with Google."
  type = object({
    client_id             = string
    client_secret_version = string
    admin_id              = optional(string)
  })
  default = null
  validation {
    condition = var.google_sso == null ? true : (
      can(regex("^[0-9]+-[a-zA-Z0-9_-]+\\.apps\\.googleusercontent\\.com$", var.google_sso.client_id)) &&
      can(regex("^[1-9][0-9]*$", var.google_sso.client_secret_version)) &&
      (var.google_sso.admin_id == null ? true : length(trimspace(var.google_sso.admin_id)) > 0)
    )
    error_message = "Use a Google OAuth client ID, a positive numeric secret version and a nonempty LiteLLM User ID."
  }
}

# Prepare an empty container before enabling SSO. Upload the value outside
# Terraform so neither state nor plans contain the OAuth client secret.
resource "google_secret_manager_secret" "google_sso" {
  project             = var.project_id
  secret_id           = "litellm-google-client-secret"
  version_destroy_ttl = "2592000s"
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_iam_member" "google_sso" {
  count     = var.google_sso == null ? 0 : 1
  project   = var.project_id
  secret_id = google_secret_manager_secret.google_sso.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

locals {
  # Admin-service only: never merge these into the shared proxy/gateway settings.
  google_sso_env = var.google_sso == null ? {} : merge(
    { GOOGLE_CLIENT_ID = var.google_sso.client_id },
    var.google_sso.admin_id == null ? {} : { PROXY_ADMIN_ID = var.google_sso.admin_id },
  )
  google_sso_secret_env = var.google_sso == null ? {} : {
    GOOGLE_CLIENT_SECRET = {
      secret  = google_secret_manager_secret.google_sso.secret_id
      version = var.google_sso.client_secret_version
    }
  }
}

output "google_sso_callback_url" {
  value       = "${local.base_url}/sso/callback"
  description = "Register this exact redirect URI on the Google OAuth web client before enabling google_sso."
}
