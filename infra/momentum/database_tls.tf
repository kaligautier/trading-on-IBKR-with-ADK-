variable "database_ca_secret_id" {
  description = "Existing PostgreSQL CA secret; no credential values enter Terraform."
  type        = string
  default     = "litellm-database-ca"
}
variable "database_ca_version" {
  description = "Pinned version of the existing PostgreSQL CA."
  type        = string
  default     = "1"
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.database_ca_version))
    error_message = "Pin a positive numeric CA secret version."
  }
}
resource "google_secret_manager_secret_iam_member" "database_ca" {
  project   = var.project_id
  secret_id = var.database_ca_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.worker.email}"
}
