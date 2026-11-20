mock_provider "google" {
  mock_data "google_project" {
    defaults = { number = "123456789012" }
  }
}
mock_provider "google-beta" {}

variables {
  project_id = "example-project"
}

run "release_registry_is_managed" {
  command = plan
  assert {
    condition     = google_artifact_registry_repository.release.repository_id == "litellm-release" && google_artifact_registry_repository.release.mode == "STANDARD_REPOSITORY"
    error_message = "Manage the audited release repository as a standard Docker repository."
  }
}
