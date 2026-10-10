mock_provider "google" {}
variables {
  project_id              = "reader-test-project"
  image                   = "europe-west1-docker.pkg.dev/reader-test-project/market-scanner/market-scanner-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  database_secret_version = "1"
  ca_secret_version       = "1"
}
run "private_bounded_reader" {
  command = plan
  assert {
    condition     = google_cloud_run_v2_service.reader.invoker_iam_disabled == false && length(google_cloud_run_v2_service_iam_member.invoker) == 0
    error_message = "No anonymous invocation may be granted."
  }
  assert {
    condition     = google_cloud_run_v2_service.reader.template[0].scaling[0].max_instance_count == 1 && google_cloud_run_v2_service.reader.template[0].scaling[0].min_instance_count == 0
    error_message = "Keep the reader bounded and able to scale to zero."
  }
  assert {
    condition     = length(google_secret_manager_secret_iam_member.reader) == 2
    error_message = "Only the reader URL and CA need Secret Manager access."
  }
}
run "reject_public_invocation" {
  command = plan
  variables {
    invoker_members = ["allUsers"]
  }
  expect_failures = [var.invoker_members]
}
run "reject_mutable_image" {
  command = plan
  variables {
    image = "europe-west1-docker.pkg.dev/reader-test-project/market-scanner/market-scanner-api:latest"
  }
  expect_failures = [var.image]
}
run "reject_mutable_secrets" {
  command = plan
  variables {
    database_secret_version = "latest"
    ca_secret_version       = "latest"
  }
  expect_failures = [var.database_secret_version, var.ca_secret_version]
}
