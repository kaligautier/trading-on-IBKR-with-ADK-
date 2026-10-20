variable "client_tools_image" {
  description = "Optional digest-pinned Python image with httpx, google-auth and google-genai for VPC inference verification jobs."
  type        = string
  default     = ""
  validation {
    condition     = var.client_tools_image == "" || can(regex("@sha256:[0-9a-f]{64}$", var.client_tools_image))
    error_message = "Use an immutable image digest, or leave the client tooling disabled."
  }
}

variable "client_key_versions" {
  description = "Client virtual-key numeric versions, returned by the governance Terraform root."
  type        = map(string)
  default     = {}
  validation {
    condition = alltrue([for name, version in var.client_key_versions :
      contains(keys(var.client_service_accounts), name) && can(regex("^[1-9][0-9]*$", version))
    ])
    error_message = "Pin a numeric secret version for a configured client identity."
  }
}

locals {
  tool_clients = local.runtime_enabled && var.client_tools_image != "" ? var.client_service_accounts : {}
}

resource "google_service_account" "key_bootstrap" {
  count        = length(var.client_service_accounts) > 0 ? 1 : 0
  project      = var.project_id
  account_id   = "litellm-key-bootstrap"
  display_name = "LiteLLM Terraform governance (never an agent identity)"
}

resource "google_secret_manager_secret_iam_member" "bootstrap_master" {
  count     = length(var.client_service_accounts) > 0 ? 1 : 0
  project   = var.project_id
  secret_id = google_secret_manager_secret.credentials["master-key"].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.key_bootstrap[0].email}"
}

resource "google_secret_manager_secret_iam_member" "bootstrap_versions" {
  for_each  = var.client_service_accounts
  project   = var.project_id
  secret_id = google_secret_manager_secret.client_key[each.key].secret_id
  role      = "roles/secretmanager.viewer"
  member    = "serviceAccount:${google_service_account.key_bootstrap[0].email}"
}

resource "google_secret_manager_secret_iam_member" "bootstrap_write" {
  for_each  = var.client_service_accounts
  project   = var.project_id
  secret_id = google_secret_manager_secret.client_key[each.key].secret_id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.key_bootstrap[0].email}"
}

# Existing keys are read ephemerally; their values never enter Terraform state.
resource "google_secret_manager_secret_iam_member" "bootstrap_read" {
  for_each  = var.client_service_accounts
  project   = var.project_id
  secret_id = google_secret_manager_secret.client_key[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.key_bootstrap[0].email}"
}

resource "google_cloud_run_v2_job" "client_verify" {
  for_each = {
    for name, email in local.tool_clients : name => email
    if contains(keys(var.client_key_versions), name)
  }
  project             = var.project_id
  location            = var.region
  name                = "litellm-verify-${each.key}"
  deletion_protection = false

  template {
    template {
      service_account = each.value
      timeout         = "900s"
      max_retries     = 0
      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = google_compute_network.private.name
          subnetwork = google_compute_subnetwork.run.name
        }
      }
      containers {
        image   = var.client_tools_image
        command = ["python"]
        args    = ["-c", file("${path.module}/tests/scanner_native.py")]
        resources {
          limits = { cpu = "1", memory = "512Mi" }
        }
        dynamic "env" {
          for_each = {
            LITELLM_BASE_URL = local.gateway_url
            LITELLM_MODEL    = var.model
          }
          content {
            name  = env.key
            value = env.value
          }
        }
        env {
          name = "LITELLM_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.client_key[each.key].secret_id
              version = var.client_key_versions[each.key]
            }
          }
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.client_key, google_cloud_run_v2_service.gateway]
}
