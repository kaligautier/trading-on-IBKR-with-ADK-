mock_provider "google" {}
mock_provider "google-beta" {}
override_resource {
  target          = google_service_account.governance
  override_during = plan
  values          = { email = "litellm-agent-governance@example-project.iam.gserviceaccount.com" }
}
variables { project_id = "example-project" }
run "governance_identity_without_client_tools" {
  command = plan
  assert {
    condition     = output.agent_governance.service_account == "litellm-agent-governance@example-project.iam.gserviceaccount.com" && google_service_account.governance.account_id == "litellm-agent-governance" && length(google_service_account.key_bootstrap) == 0
    error_message = "Governance must keep its deployed identity without a tooling image or runner."
  }
  assert {
    condition     = toset(keys(google_secret_manager_secret_iam_member.governance_read)) == toset(["litellm-master-key"]) && toset(keys(google_secret_manager_secret_iam_member.governance_versions)) == toset(["litellm-master-key"]) && length(google_secret_manager_secret_iam_member.governance_write) == 0 && google_secret_manager_secret_iam_member.governance_read["litellm-master-key"].role == "roles/secretmanager.secretAccessor" && google_secret_manager_secret_iam_member.governance_read["litellm-master-key"].member == "serviceAccount:litellm-agent-governance@example-project.iam.gserviceaccount.com"
    error_message = "Without clients, governance may only read the master key."
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
    condition = toset(keys(google_secret_manager_secret_iam_member.governance_write)) == toset(["litellm-client-scanner", "litellm-client-momentum"]) && alltrue([for grants in [google_secret_manager_secret_iam_member.governance_read, google_secret_manager_secret_iam_member.governance_versions] :
      toset(keys(grants)) == toset(["litellm-master-key", "litellm-client-scanner", "litellm-client-momentum"])]) && alltrue(flatten([for name in ["scanner", "momentum"] : [
        google_secret_manager_secret_iam_member.governance_read["litellm-client-${name}"].role == "roles/secretmanager.secretAccessor",
        google_secret_manager_secret_iam_member.governance_versions["litellm-client-${name}"].role == "roles/secretmanager.viewer",
        google_secret_manager_secret_iam_member.governance_write["litellm-client-${name}"].role == "roles/secretmanager.secretVersionAdder",
        alltrue([for grant in [google_secret_manager_secret_iam_member.governance_read["litellm-client-${name}"], google_secret_manager_secret_iam_member.governance_versions["litellm-client-${name}"], google_secret_manager_secret_iam_member.governance_write["litellm-client-${name}"]] :
        grant.secret_id == "litellm-client-${name}" && grant.member == "serviceAccount:litellm-agent-governance@example-project.iam.gserviceaccount.com"])
    ]]))
    error_message = "Governance needs scoped read, metadata and version-add access for every configured client."
  }
}

run "configurable_governance_identity" {
  command = plan
  variables {
    governance_service_account_id = "litellm-governance"
  }
  assert {
    condition     = google_service_account.governance.account_id == "litellm-governance"
    error_message = "A new environment may choose another governance identity."
  }
}
