mock_provider "google" {}

variables {
  project_id           = "example-project"
  github_repository    = "example-owner/example-repo"
  github_repository_id = "111"
  github_owner_id      = "222"
  billing_account_id   = "ABCDEF-012345-6789AB"
}

run "identity_is_read_only" {
  command = plan
  assert {
    condition     = toset([for grant in google_project_iam_member.read : grant.role]) == toset(["roles/viewer", "roles/iam.securityReviewer"])
    error_message = "The drift identity may only hold read roles."
  }
  assert {
    condition     = google_storage_bucket_iam_member.state_reader.role == "roles/storage.objectViewer"
    error_message = "State is read, never written."
  }
}

run "federation_is_pinned_to_the_main_workflow" {
  command = plan
  assert {
    condition = alltrue([
      strcontains(google_iam_workload_identity_pool_provider.github.attribute_condition, "assertion.repository_id == '111'"),
      strcontains(google_iam_workload_identity_pool_provider.github.attribute_condition, "assertion.repository_owner_id == '222'"),
      strcontains(google_iam_workload_identity_pool_provider.github.attribute_condition, "assertion.ref == 'refs/heads/main'"),
      strcontains(google_iam_workload_identity_pool_provider.github.attribute_condition, "example-owner/example-repo/.github/workflows/infra-drift.yml@refs/heads/main"),
      strcontains(google_iam_workload_identity_pool_provider.github.attribute_condition, "assertion.event_name in ['schedule', 'workflow_dispatch']"),
      strcontains(google_iam_workload_identity_pool_provider.github.attribute_condition, "assertion.runner_environment == 'github-hosted'"),
    ])
    error_message = "Only the reviewed workflow on main, in this repository, may impersonate the drift identity."
  }
}

run "inputs_secret_is_protected_and_unreadable_by_others" {
  command = plan
  assert {
    condition     = google_secret_manager_secret.inputs.secret_id == "infra-drift-inputs" && google_secret_manager_secret_iam_member.inputs.role == "roles/secretmanager.secretAccessor"
    error_message = "Only the drift identity reads the plan inputs."
  }
}

run "billing_access_is_read_only_and_account_scoped" {
  command = plan
  assert {
    condition     = google_billing_account_iam_member.billing_reader.role == "roles/billing.viewer" && google_billing_account_iam_member.billing_reader.billing_account_id == "ABCDEF-012345-6789AB"
    error_message = "The drift identity may only view the billing account."
  }
}

run "reject_malformed_billing_account" {
  command = plan
  variables { billing_account_id = "not-an-id" }
  expect_failures = [var.billing_account_id]
}
