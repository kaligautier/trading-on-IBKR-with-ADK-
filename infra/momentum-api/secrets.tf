variable "adopt_existing_secrets" {
  description = "First apply only: adopt the reader URL and CA secrets that existed before Terraform managed them. Leave false for a new project."
  type        = bool
  default     = false
}

locals {
  managed_secrets = toset([var.database_secret_id, var.ca_secret_id])
}

# Only the containers are managed. Upload the values outside Terraform.
resource "google_secret_manager_secret" "reader" {
  for_each  = local.managed_secrets
  project   = var.project_id
  secret_id = each.value
  labels    = { application = "momentum", component = "reader" }
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

import {
  for_each = var.adopt_existing_secrets ? local.managed_secrets : toset([])
  to       = google_secret_manager_secret.reader[each.value]
  id       = "projects/${var.project_id}/secrets/${each.value}"
}
