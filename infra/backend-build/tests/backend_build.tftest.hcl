mock_provider "google" {}

run "builder_is_narrowly_scoped" {
  command = plan
  assert {
    condition     = google_service_account.builder.account_id == "backend-builder"
    error_message = "Backend builds need their own identity, never the default compute account."
  }
  assert {
    condition     = toset(keys(google_artifact_registry_repository_iam_member.publisher)) == toset(["market-scanner", "momentum"])
    error_message = "Publish only to the backend image repositories."
  }
  assert {
    condition     = alltrue([for grant in google_artifact_registry_repository_iam_member.publisher : grant.role == "roles/artifactregistry.writer"])
    error_message = "Repository grants must stay at writer level."
  }
  assert {
    condition     = google_project_iam_member.build_logs.role == "roles/logging.logWriter"
    error_message = "The only project-level grant is log writing."
  }
  assert {
    condition     = google_storage_bucket_iam_member.source_reader.role == "roles/storage.objectViewer"
    error_message = "The builder only reads its staged sources."
  }
}

run "sources_are_private_and_short_lived" {
  command = plan
  assert {
    condition     = google_storage_bucket.sources.public_access_prevention == "enforced" && google_storage_bucket.sources.uniform_bucket_level_access
    error_message = "Staged sources must never be public."
  }
  assert {
    condition     = one([for rule in google_storage_bucket.sources.lifecycle_rule : one([for c in rule.condition : c.age])]) == 7 && !google_storage_bucket.sources.force_destroy
    error_message = "Delete staged sources after a week without force-destroying the bucket."
  }
}
