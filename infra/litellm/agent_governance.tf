variable "agent_governance" {
  description = "Optional private Terraform runner. Existing team/key IDs and secret versions are non-secret adoption inputs."
  type = object({
    runner_image = string
    team_id      = optional(string, "agents")
    import_team  = optional(bool, false)
    state_prefix = optional(string, "agents")
    agents = map(object({
      max_budget            = optional(number, 3)
      budget_duration       = optional(string, "1d")
      rpm_limit             = optional(number, 10)
      tpm_limit             = optional(number, 100000)
      max_parallel_requests = optional(number, 2)
      secret_version        = optional(string)
      existing_token_id     = optional(string)
    }))
  })
  default = null
  validation {
    condition     = var.agent_governance == null ? true : can(regex("@sha256:[0-9a-f]{64}$", var.agent_governance.runner_image))
    error_message = "Pin the Terraform runner image to an immutable digest."
  }
}
locals {
  governance_enabled = var.agent_governance != null
  governance_secrets = local.governance_enabled ? {
    for name in keys(var.agent_governance.agents) :
    "litellm-client-${name}" => google_secret_manager_secret.client_key[name].secret_id
  } : {}
  governance_read_secrets = local.governance_enabled ? merge(local.governance_secrets, {
    "litellm-master-key" = google_secret_manager_secret.credentials["master-key"].secret_id
  }) : {}
  governance_files = local.governance_enabled ? merge({
    for name in ["main.tf", "variables.tf", "moved.tf", ".terraform.lock.hcl", "policy/main.tf", "policy/.terraform.lock.hcl"] :
    name => file("${path.module}/governance/${name}")
    }, {
    "governance.auto.tfvars.json" = jsonencode({
      project_id         = var.project_id
      gateway_url        = local.gateway_url
      master_key_version = var.secret_versions["master-key"]
      models             = [for model in yamldecode(local.proxy_config).model_list : model.model_name]
      team_id            = var.agent_governance.team_id
      import_team        = var.agent_governance.import_team
      agents             = var.agent_governance.agents
    })
    "backend.hcl" = "bucket = \"${google_storage_bucket.governance_state[0].name}\"\nprefix = \"${var.agent_governance.state_prefix}\"\n"
  }) : {}
  governance_command = chomp(templatefile("${path.module}/templates/governance.sh.tftpl", {
    files = local.governance_files
  }))
}
resource "google_service_account" "governance" {
  count        = local.governance_enabled ? 1 : 0
  project      = var.project_id
  account_id   = "litellm-agent-governance"
  display_name = "LiteLLM team and key Terraform provisioning"
}
resource "google_storage_bucket" "governance_state" {
  count                       = local.governance_enabled ? 1 : 0
  project                     = var.project_id
  name                        = "${var.project_id}-litellm-agents-state"
  location                    = upper(var.region)
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  versioning { enabled = true }
  lifecycle { prevent_destroy = true }
}
resource "google_storage_bucket_iam_member" "governance_state" {
  count  = local.governance_enabled ? 1 : 0
  bucket = google_storage_bucket.governance_state[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.governance[0].email}"
}
# Keep the existing secret and versions when attaching an application identity.
moved {
  from = google_secret_manager_secret.momentum_key[0]
  to   = google_secret_manager_secret.client_key["momentum"]
}
resource "google_secret_manager_secret_iam_member" "governance_read" {
  for_each  = local.governance_read_secrets
  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.governance[0].email}"
}
resource "google_secret_manager_secret_iam_member" "governance_versions" {
  for_each  = local.governance_read_secrets
  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.viewer"
  member    = "serviceAccount:${google_service_account.governance[0].email}"
}
resource "google_secret_manager_secret_iam_member" "governance_write" {
  for_each  = local.governance_secrets
  project   = var.project_id
  secret_id = each.value
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.governance[0].email}"
}
moved {
  from = google_secret_manager_secret_iam_member.governance_write[0]
  to   = google_secret_manager_secret_iam_member.governance_write["litellm-client-momentum"]
}
resource "google_cloud_run_v2_job" "agent_governance" {
  count               = local.governance_enabled && local.runtime_enabled ? 1 : 0
  project             = var.project_id
  location            = var.region
  name                = "litellm-agent-governance"
  deletion_protection = false
  template {
    template {
      service_account = google_service_account.governance[0].email
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
        image   = var.agent_governance.runner_image
        command = ["sh"]
        args    = ["-ec", local.governance_command]
        resources { limits = { cpu = "1", memory = "1Gi" } }
        env {
          name  = "TF_IN_AUTOMATION"
          value = "true"
        }
        env {
          name  = "GOVERNANCE_ACTION"
          value = "plan"
        }
      }
    }
  }
  depends_on = [google_cloud_run_v2_service.gateway,
    google_storage_bucket_iam_member.governance_state,
    google_secret_manager_secret_iam_member.governance_read,
    google_secret_manager_secret_iam_member.governance_versions,
    google_secret_manager_secret_iam_member.governance_write,
    google_secret_manager_secret.client_key,
  ]
}
output "governance_job" {
  value = try(google_cloud_run_v2_job.agent_governance[0].name, null)
}
