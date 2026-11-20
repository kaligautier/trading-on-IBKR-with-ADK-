terraform {
  required_version = ">= 1.9, < 2.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
}

variable "project_id" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Use a GCP project ID."
  }
}

variable "github_repository" {
  description = "Owner/name of the repository whose nightly workflow may plan the infrastructure."
  type        = string
  validation {
    condition     = can(regex("^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", var.github_repository))
    error_message = "Use owner/name."
  }
}

variable "github_repository_id" {
  description = "Immutable numeric repository ID."
  type        = string
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.github_repository_id))
    error_message = "Use the numeric repository ID."
  }
}

variable "github_owner_id" {
  description = "Immutable numeric owner ID."
  type        = string
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.github_owner_id))
    error_message = "Use the numeric owner ID."
  }
}

variable "billing_account_id" {
  description = "Billing account whose budgets the nightly plan reads (XXXXXX-XXXXXX-XXXXXX). Keep it in an ignored billing.local.tfvars: the repository is public."
  type        = string
  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account_id))
    error_message = "Use a billing account ID such as 012345-6789AB-CDEF01."
  }
}

variable "state_bucket" {
  type    = string
  default = "preprod-deep-copy-tfstate"
}

variable "workflow_file" {
  type    = string
  default = "infra-drift.yml"
}

locals {
  workflow_ref = "${var.github_repository}/.github/workflows/${var.workflow_file}@refs/heads/main"
}

# Existing project APIs stay enabled if this root is destroyed.
resource "google_project_service" "apis" {
  for_each           = toset(["sts.googleapis.com", "iamcredentials.googleapis.com"])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Read-only identity: it can refresh a plan but never change infrastructure.
resource "google_service_account" "drift" {
  project      = var.project_id
  account_id   = "infra-drift"
  display_name = "Nightly Terraform drift detection (read-only)"
}

# serviceUsageConsumer lets providers that set user_project_override (budget-guard) bill their
# calls to this project; it grants no permission on the APIs themselves.
resource "google_project_iam_member" "read" {
  for_each = toset(["roles/viewer", "roles/iam.securityReviewer", "roles/serviceusage.serviceUsageConsumer"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.drift.email}"
}

# Refreshing google_billing_budget needs billing.budgets.get on the billing account,
# which no project-level role grants. Read-only, and scoped to this one account.
resource "google_billing_account_iam_member" "billing_reader" {
  billing_account_id = var.billing_account_id
  role               = "roles/billing.viewer"
  member             = "serviceAccount:${google_service_account.drift.email}"
}

resource "google_storage_bucket_iam_member" "state_reader" {
  bucket = var.state_bucket
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.drift.email}"
}

# Plan inputs that must stay out of the public repository (invoker and IAP identities,
# SSO, key fingerprints, alert address). Only the container is managed here; the value is
# a JSON map {root: {file: content}} uploaded with scripts/build_inputs.py.
resource "google_secret_manager_secret" "inputs" {
  project   = var.project_id
  secret_id = "infra-drift-inputs"
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "inputs" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.inputs.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.drift.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "infra-drift"
  display_name              = "Nightly drift detection"
  depends_on                = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  attribute_mapping = {
    "google.subject"          = "assertion.sub"
    "attribute.repository_id" = "assertion.repository_id"
  }
  attribute_condition = join(" && ", [
    "assertion.repository_id == '${var.github_repository_id}'",
    "assertion.repository_owner_id == '${var.github_owner_id}'",
    "assertion.ref == 'refs/heads/main'",
    "assertion.workflow_ref == '${local.workflow_ref}'",
    "assertion.event_name in ['schedule', 'workflow_dispatch']",
    "assertion.runner_environment == 'github-hosted'",
  ])
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github" {
  service_account_id = google_service_account.drift.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${var.github_repository_id}"
}

output "repository_variables" {
  description = "Set these as GitHub Actions repository variables."
  value = {
    GCP_PROJECT_ID                   = var.project_id
    DRIFT_WORKLOAD_IDENTITY_PROVIDER = google_iam_workload_identity_pool_provider.github.name
    DRIFT_SERVICE_ACCOUNT            = google_service_account.drift.email
    DRIFT_STATE_BUCKET               = var.state_bucket
  }
}
