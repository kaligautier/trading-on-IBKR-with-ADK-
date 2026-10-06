variable "client_service_accounts" {
  description = "Existing application identities allowed through IAP; keys are provisioned outside Terraform."
  type        = map(string)
  default     = {}
  validation {
    condition = alltrue([for name, email in var.client_service_accounts :
      can(regex("^[a-z][a-z0-9-]{2,40}$", name)) &&
      can(regex("^[a-z][a-z0-9-]+@${var.project_id}\\.iam\\.gserviceaccount\\.com$", email))
    ])
    error_message = "Use explicit service accounts in this project and safe client names."
  }
}

resource "google_project_service" "iam_credentials" {
  project            = var.project_id
  service            = "iamcredentials.googleapis.com"
  disable_on_destroy = false
}

resource "google_iap_web_cloud_run_service_iam_member" "clients" {
  for_each               = local.runtime_enabled ? var.client_service_accounts : {}
  project                = var.project_id
  location               = var.region
  cloud_run_service_name = google_cloud_run_v2_service.litellm[0].name
  role                   = "roles/iap.httpsResourceAccessor"
  member                 = "serviceAccount:${each.value}"
}

# A caller can sign only as itself, never as the gateway or another identity.
resource "google_service_account_iam_member" "client_signer" {
  for_each           = var.client_service_accounts
  service_account_id = "projects/${var.project_id}/serviceAccounts/${each.value}"
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${each.value}"
}

resource "google_secret_manager_secret" "client_key" {
  for_each  = var.client_service_accounts
  project   = var.project_id
  secret_id = "litellm-client-${each.key}"
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_iam_member" "client_key" {
  for_each  = var.client_service_accounts
  project   = var.project_id
  secret_id = google_secret_manager_secret.client_key[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}
variable "client_operator_members" {
  description = "Explicit operators allowed to impersonate client SAs for bootstrap and local tests."
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for member in var.client_operator_members : can(regex("^user:[^ ]+@[^ ]+$", member))])
    error_message = "Use explicit user:email members."
  }
}

resource "google_service_account_iam_member" "client_operator" {
  for_each = {
    for pair in setproduct(keys(var.client_service_accounts), var.client_operator_members) :
    "${pair[0]}:${pair[1]}" => { account = var.client_service_accounts[pair[0]], member = pair[1] }
  }
  service_account_id = "projects/${var.project_id}/serviceAccounts/${each.value.account}"
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = each.value.member
}
