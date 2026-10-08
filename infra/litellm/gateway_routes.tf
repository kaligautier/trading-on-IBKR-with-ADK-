variable "gateway_filter_digest" {
  description = "NGINX unprivileged stable-alpine image index, verified against GHCR on 2026-10-07."
  type        = string
  default     = "sha256:15c994d10d6d78658721c3bcafff14cb281fba2a4bdf9d5ba92c416a472516e3"
  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.gateway_filter_digest))
    error_message = "Use an immutable gateway filter image digest."
  }
}

locals {
  gateway_filter_image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.litellm.repository_id}/nginx/nginx-unprivileged@${var.gateway_filter_digest}"
}

resource "google_secret_manager_secret" "gateway_routes" {
  project             = var.project_id
  secret_id           = "litellm-gateway-routes"
  version_destroy_ttl = "2592000s"
  replication {
    auto {}
  }
  lifecycle { prevent_destroy = true }
}

resource "google_secret_manager_secret_version" "gateway_routes" {
  secret          = google_secret_manager_secret.gateway_routes.id
  secret_data     = file("${path.module}/config/gateway-nginx.conf")
  deletion_policy = "ABANDON"
  lifecycle { create_before_destroy = true }
}

resource "google_secret_manager_secret_iam_member" "gateway_routes" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.gateway_routes.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}
