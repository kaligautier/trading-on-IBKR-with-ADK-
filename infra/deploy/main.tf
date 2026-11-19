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
  description = "Owner/name of the repository whose reviewed workflow may deploy."
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

variable "workflow_file" {
  type    = string
  default = "deploy.yml"
}

variable "environment_name" {
  description = "GitHub environment holding the required reviewers; the token only carries it for jobs that use it."
  type        = string
  default     = "preprod-deploy"
}

variable "state_bucket" {
  type    = string
  default = "preprod-deep-copy-tfstate"
}

variable "state_prefixes" {
  description = "State prefixes of the roots the deployer may write (one per deployable root)."
  type        = set(string)
  default     = ["preprod/runtime", "preprod/reader", "preprod/momentum-api", "preprod/momentum"]
}

variable "inputs_secret" {
  description = "Secret holding the private plan inputs, shared with the drift check."
  type        = string
  default     = "infra-drift-inputs"
}

variable "build_service_account" {
  description = "Backend image builder that the deployer submits builds as."
  type        = string
  default     = "backend-builder"
}

variable "build_sources_bucket" {
  type    = string
  default = "preprod-deep-copy-backend-build-sources"
}

variable "runtime_service_accounts" {
  description = "Runtime identities of the services and jobs that releases update."
  type        = map(string)
  validation {
    condition = alltrue([for email in values(var.runtime_service_accounts) :
      can(regex("^[a-z][a-z0-9-]+@${var.project_id}\\.iam\\.gserviceaccount\\.com$", email))
    ])
    error_message = "Use service accounts of this project."
  }
}

locals {
  workflow_ref = "${var.github_repository}/.github/workflows/${var.workflow_file}@refs/heads/main"
  state_condition = join(" || ", [
    for prefix in sort(tolist(var.state_prefixes)) :
    "resource.name.startsWith('projects/_/buckets/${var.state_bucket}/objects/${prefix}/')"
  ])
}

resource "google_project_service" "apis" {
  for_each           = toset(["sts.googleapis.com", "iamcredentials.googleapis.com", "cloudbuild.googleapis.com"])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Writes only image updates of Cloud Run services and jobs. The workflow refuses any other
# plan before applying; these grants are the second barrier (no IAM policy, secret, bucket,
# network or project-level write).
resource "google_service_account" "deploy" {
  project      = var.project_id
  account_id   = "infra-deployer"
  display_name = "Reviewed application image releases"
}

resource "google_project_iam_member" "roles" {
  for_each = toset([
    "roles/viewer",                   # refresh a plan
    "roles/iam.securityReviewer",     # refresh IAM bindings
    "roles/run.developer",            # update services and jobs, never their IAM policy
    "roles/cloudbuild.builds.editor", # submit and read builds
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

# Run builds as the dedicated builder, never as the default compute identity.
resource "google_service_account_iam_member" "build_as_builder" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.build_service_account}@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account_iam_member" "act_as_runtime" {
  for_each           = var.runtime_service_accounts
  service_account_id = "projects/${var.project_id}/serviceAccounts/${each.value}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_storage_bucket_iam_member" "stage_sources" {
  for_each = toset(["roles/storage.objectUser", "roles/storage.legacyBucketReader"])
  bucket   = var.build_sources_bucket
  role     = each.value
  member   = "serviceAccount:${google_service_account.deploy.email}"
}

# State of the deployable roots only: read, write and lock.
resource "google_storage_bucket_iam_member" "state_writer" {
  bucket = var.state_bucket
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.deploy.email}"
  condition {
    title      = "deployable-roots-state"
    expression = local.state_condition
  }
}

# Lists object names (not contents) and reads bucket metadata for the backend.
resource "google_storage_bucket_iam_member" "state_lister" {
  bucket = var.state_bucket
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_secret_manager_secret_iam_member" "inputs" {
  project   = var.project_id
  secret_id = var.inputs_secret
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "infra-deploy"
  display_name              = "Reviewed application releases"
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
  # Only the reviewed workflow on main, started by hand, in the protected environment.
  attribute_condition = join(" && ", [
    "assertion.repository_id == '${var.github_repository_id}'",
    "assertion.repository_owner_id == '${var.github_owner_id}'",
    "assertion.ref == 'refs/heads/main'",
    "assertion.workflow_ref == '${local.workflow_ref}'",
    "assertion.event_name == 'workflow_dispatch'",
    "assertion.environment == '${var.environment_name}'",
    "assertion.runner_environment == 'github-hosted'",
  ])
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository_id/${var.github_repository_id}"
}

output "repository_variables" {
  description = "Set these as GitHub Actions repository variables."
  value = {
    DEPLOY_WORKLOAD_IDENTITY_PROVIDER = google_iam_workload_identity_pool_provider.github.name
    DEPLOY_SERVICE_ACCOUNT            = google_service_account.deploy.email
  }
}
