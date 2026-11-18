variable "adopt_existing_release_registry" {
  description = "First apply only: adopt the litellm-release repository that existed before Terraform managed it. Leave false for a new project."
  type        = bool
  default     = false
}

# Holds the audited, security-patched images built by scripts/build_images.py.
resource "google_artifact_registry_repository" "release" {
  project       = var.project_id
  location      = var.region
  repository_id = "litellm-release"
  description   = "Security-audited LiteLLM release images"
  format        = "DOCKER"
  mode          = "STANDARD_REPOSITORY"
  lifecycle {
    prevent_destroy = true
  }
}

import {
  for_each = var.adopt_existing_release_registry ? toset(["litellm-release"]) : toset([])
  to       = google_artifact_registry_repository.release
  id       = "projects/${var.project_id}/locations/${var.region}/repositories/${each.value}"
}
