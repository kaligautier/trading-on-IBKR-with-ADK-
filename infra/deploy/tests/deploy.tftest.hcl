mock_provider "google" {}
variables {
  project_id           = "example-project"
  github_repository    = "owner/repo"
  github_repository_id = "1"
  github_owner_id      = "2"
  runtime_service_accounts = {
    app = "app-runtime@example-project.iam.gserviceaccount.com"
  }
}

run "only_the_reviewed_workflow_in_the_protected_environment" {
  command = plan
  assert {
    condition = alltrue([for clause in [
      "assertion.repository_id == '1'",
      "assertion.repository_owner_id == '2'",
      "assertion.ref == 'refs/heads/main'",
      "assertion.workflow_ref == 'owner/repo/.github/workflows/deploy.yml@refs/heads/main'",
      "assertion.event_name == 'workflow_dispatch'",
      "assertion.environment == 'preprod-deploy'",
      "assertion.runner_environment == 'github-hosted'",
    ] : strcontains(google_iam_workload_identity_pool_provider.github.attribute_condition, clause)])
    error_message = "The provider must accept only the manual deploy workflow on main, in its environment."
  }
}

run "no_broad_or_iam_writing_role" {
  command = plan
  assert {
    condition = toset(keys(google_project_iam_member.roles)) == toset([
      "roles/viewer", "roles/iam.securityReviewer", "roles/run.developer", "roles/cloudbuild.builds.editor",
    ])
    error_message = "The deployer holds read access, Cloud Run updates and builds, nothing else at project level."
  }
}

run "acts_only_as_the_listed_identities" {
  command = plan
  assert {
    condition     = toset(keys(google_service_account_iam_member.act_as_runtime)) == toset(["app"]) && google_service_account_iam_member.build_as_builder.role == "roles/iam.serviceAccountUser"
    error_message = "actAs is limited to the runtime identities and the image builder."
  }
}

run "state_write_is_limited_to_the_deployable_roots" {
  command = plan
  assert {
    condition     = length(split(" || ", google_storage_bucket_iam_member.state_writer.condition[0].expression)) == 4
    error_message = "State write access must cover exactly the four deployable roots."
  }
  assert {
    condition     = google_storage_bucket_iam_member.state_writer.role == "roles/storage.objectUser" && google_storage_bucket_iam_member.state_lister.role == "roles/storage.legacyBucketReader"
    error_message = "The deployer writes objects of its roots and only lists the rest."
  }
}

run "reject_a_foreign_runtime_identity" {
  command = plan
  variables {
    runtime_service_accounts = { app = "app-runtime@other-project.iam.gserviceaccount.com" }
  }
  expect_failures = [var.runtime_service_accounts]
}
