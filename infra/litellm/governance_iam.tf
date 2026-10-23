# Terraform governance reads credentials back; the legacy bootstrap job cannot.
resource "google_service_account" "governance" {
  project      = var.project_id
  account_id   = "litellm-governance"
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
