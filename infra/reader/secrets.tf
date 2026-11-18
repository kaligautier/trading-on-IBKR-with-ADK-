variable "adopt_existing_secret" {
  description = "First apply only: adopt the reader URL secret that existed before Terraform managed it. Leave false for a new project."
  type        = bool
  default     = false
}

# Only the container is managed. Upload the URL value outside Terraform.
resource "google_secret_manager_secret" "database" {
  project   = var.project_id
  secret_id = var.database_secret_id
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

import {
  for_each = var.adopt_existing_secret ? toset([var.database_secret_id]) : toset([])
  to       = google_secret_manager_secret.database
  id       = "projects/${var.project_id}/secrets/${each.value}"
}
