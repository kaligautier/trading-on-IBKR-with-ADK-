mock_provider "google" {
  mock_data "google_project" { defaults = { number = "123456789012" } }
}
mock_provider "google-beta" {}
variables {
  project_id      = "example-project"
  secret_versions = { master-key = "1" }
  agent_governance = {
    runner_image = "registry.example.com/terraform@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    agents       = { momentum = {}, future-agent = {} }
  }
}
run "legacy_momentum_secret" {
  command   = apply
  state_key = "momentum"
  module { source = "./tests/fixtures/legacy-momentum" }
}
run "adopt_secret_without_application_identity" {
  command   = apply
  state_key = "momentum"
  assert {
    condition = (
      google_secret_manager_secret.client_key["momentum"].id == run.legacy_momentum_secret.secret_id &&
      length(google_secret_manager_secret.client_key) == 2 &&
      length(google_secret_manager_secret_iam_member.client_key) == 0
    )
    error_message = "Governance must adopt the legacy secret and prepare new agents without application access."
  }
}
run "attach_application_identity_without_replacing_secret" {
  command   = apply
  state_key = "momentum"
  variables {
    client_service_accounts = { momentum = "momentum@example-project.iam.gserviceaccount.com" }
  }
  assert {
    condition = (
      google_secret_manager_secret.client_key["momentum"].id == run.legacy_momentum_secret.secret_id &&
      google_secret_manager_secret_iam_member.client_key["momentum"].secret_id == "litellm-client-momentum" &&
      length(google_secret_manager_secret_iam_member.client_key) == 1
    )
    error_message = "Attaching an application identity must retain the secret and grant access only to that agent."
  }
}
