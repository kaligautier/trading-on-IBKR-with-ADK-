mock_provider "google" {}
mock_provider "google-beta" {}
override_resource {
  target          = google_service_account.governance
  override_during = plan
  values          = { email = "litellm-governance@example-project.iam.gserviceaccount.com" }
}
variables { project_id = "example-project" }
run "governance_identity_without_client_tools" {
  command = plan
  assert {
    condition     = output.agent_governance.service_account == "litellm-governance@example-project.iam.gserviceaccount.com" && length(google_service_account.key_bootstrap) == 0
    error_message = "Governance must have its own usable identity without a tooling image."
  }
  assert {
    condition     = google_secret_manager_secret_iam_member.governance_master.role == "roles/secretmanager.secretAccessor" && google_secret_manager_secret_iam_member.governance_master.secret_id == "litellm-master-key" && google_secret_manager_secret_iam_member.governance_master.member == "serviceAccount:litellm-governance@example-project.iam.gserviceaccount.com"
    error_message = "Grant the governance identity read access to the master key only."
  }
  assert {
    condition     = length(google_secret_manager_secret_iam_member.governance_client) == 0 && length(google_secret_manager_secret_iam_member.governance_versions) == 0 && length(google_secret_manager_secret_iam_member.governance_write) == 0
    error_message = "No configured clients means no client credential grants."
  }
}
run "governance_can_read_and_persist_only_configured_client_keys" {
  command = plan
  variables {
    client_service_accounts = {
      scanner  = "scanner@example-project.iam.gserviceaccount.com"
      momentum = "momentum@example-project.iam.gserviceaccount.com"
    }
  }
  assert {
    condition = alltrue([for grants in [google_secret_manager_secret_iam_member.governance_client, google_secret_manager_secret_iam_member.governance_versions, google_secret_manager_secret_iam_member.governance_write] :
      toset(keys(grants)) == toset(["scanner", "momentum"])]) && alltrue(flatten([for name in ["scanner", "momentum"] : [
        google_secret_manager_secret_iam_member.governance_client[name].role == "roles/secretmanager.secretAccessor",
        google_secret_manager_secret_iam_member.governance_versions[name].role == "roles/secretmanager.viewer",
        google_secret_manager_secret_iam_member.governance_write[name].role == "roles/secretmanager.secretVersionAdder",
        alltrue([for grant in [google_secret_manager_secret_iam_member.governance_client[name], google_secret_manager_secret_iam_member.governance_versions[name], google_secret_manager_secret_iam_member.governance_write[name]] :
        grant.secret_id == "litellm-client-${name}" && grant.member == "serviceAccount:litellm-governance@example-project.iam.gserviceaccount.com"])
    ]]))
    error_message = "Governance needs scoped read, metadata and version-add access for every configured client."
  }
}
