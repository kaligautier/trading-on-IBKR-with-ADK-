variable "governance_service_account_id" {
  description = "Governance identity account ID; retain the existing ID during runtime-only releases."
  type        = string
  default     = "litellm-governance"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.governance_service_account_id))
    error_message = "Use a valid existing or new Google service account ID."
  }
}

# Terraform governance reads credentials back; the legacy bootstrap job cannot.
resource "google_service_account" "governance" {
  project      = var.project_id
  account_id   = var.governance_service_account_id
  display_name = "LiteLLM Terraform governance"
}

resource "google_secret_manager_secret_iam_member" "governance_master" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.credentials["master-key"].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.governance.email}"
}

resource "google_secret_manager_secret_iam_member" "governance_client" {
  for_each  = var.client_service_accounts
  project   = var.project_id
  secret_id = google_secret_manager_secret.client_key[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.governance.email}"
}

resource "google_secret_manager_secret_iam_member" "governance_versions" {
  for_each  = var.client_service_accounts
  project   = var.project_id
  secret_id = google_secret_manager_secret.client_key[each.key].secret_id
  role      = "roles/secretmanager.viewer"
  member    = "serviceAccount:${google_service_account.governance.email}"
}

resource "google_secret_manager_secret_iam_member" "governance_write" {
  for_each  = var.client_service_accounts
  project   = var.project_id
  secret_id = google_secret_manager_secret.client_key[each.key].secret_id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.governance.email}"
}
