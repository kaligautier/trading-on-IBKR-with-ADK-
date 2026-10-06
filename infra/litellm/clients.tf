variable "client_service_accounts" {
  description = "Existing application identities allowed to read their private-gateway virtual keys."
  type        = map(string)
  default     = {}
  validation {
    condition = alltrue([for name, email in var.client_service_accounts :
      can(regex("^[a-z][a-z0-9-]{2,40}$", name)) &&
      can(regex("^[a-z][a-z0-9-]+@${var.project_id}\\.iam\\.gserviceaccount\\.com$", email))
    ])
    error_message = "Use explicit service accounts in this project and safe client names."
  }
}

resource "google_secret_manager_secret" "client_key" {
  for_each            = var.client_service_accounts
  project             = var.project_id
  secret_id           = "litellm-client-${each.key}"
  version_destroy_ttl = "2592000s"
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_iam_member" "client_key" {
  for_each  = var.client_service_accounts
  project   = var.project_id
  secret_id = google_secret_manager_secret.client_key[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}
