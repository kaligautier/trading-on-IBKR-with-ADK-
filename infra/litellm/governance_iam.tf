variable "governance_service_account_id" {
  description = "Governance identity account ID; retain the existing ID during runtime-only releases."
  type        = string
  default     = "litellm-agent-governance"
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
