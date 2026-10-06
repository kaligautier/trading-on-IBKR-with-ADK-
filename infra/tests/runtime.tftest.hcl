mock_provider "google" {}

override_resource {
  target          = google_service_account.scanner
  override_during = plan
  values = {
    email = "market-scanner-adk@preprod-deep-copy.iam.gserviceaccount.com"
  }
}

variables {
  project_id              = "preprod-deep-copy"
  image                   = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/market-scanner-adk@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  database_secret_version = "1"
  invoker_members         = ["serviceAccount:caller@preprod-deep-copy.iam.gserviceaccount.com"]
}

run "private_runtime" {
  command = plan

  assert {
    condition     = google_cloud_run_v2_service.scanner.invoker_iam_disabled == false
    error_message = "ADK routes must remain behind Cloud Run IAM."
  }
  assert {
    condition = (
      google_cloud_run_v2_service.scanner.template[0].scaling[0].max_instance_count == 1 &&
      google_cloud_run_v2_service.scanner.template[0].max_instance_request_concurrency == 1
    )
    error_message = "Respect the existing small PostgreSQL writer connection budget."
  }
  assert {
    condition = (
      google_cloud_run_v2_service.scanner.template[0].containers[0].ports[0].container_port == 8000 &&
      google_cloud_run_v2_service.scanner.template[0].containers[0].startup_probe[0].http_get[0].path == "/health"
    )
    error_message = "Cloud Run must match the existing server port and health endpoint."
  }
  assert {
    condition = alltrue([
      for env in google_cloud_run_v2_service.scanner.template[0].containers[0].env :
      env.name != "GOOGLE_API_KEY" && env.name != "GOOGLE_APPLICATION_CREDENTIALS"
    ])
    error_message = "Use the attached runtime service account for Vertex AI; never mount a private SA key."
  }
  assert {
    condition = (
      google_project_iam_member.vertex.role == "roles/aiplatform.user" &&
      google_project_iam_member.vertex.member == "serviceAccount:${google_service_account.scanner.email}" &&
      [for env in google_cloud_run_v2_service.scanner.template[0].containers[0].env :
      env.value if env.name == "GOOGLE_GENAI_USE_VERTEXAI"] == ["true"]
    )
    error_message = "The scanner must call Vertex AI directly with its runtime identity."
  }
}

run "reject_foreign_project_image" {
  command = plan
  variables {
    image = "europe-west1-docker.pkg.dev/another-project/market-scanner/market-scanner-adk@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
  expect_failures = [var.image]
}

run "reject_mutable_image" {
  command = plan
  variables {
    image = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/market-scanner-adk:latest"
  }
  expect_failures = [var.image]
}

run "reject_public_invocation" {
  command = plan
  variables {
    invoker_members = ["allUsers"]
  }
  expect_failures = [var.invoker_members]
}

run "reject_mutable_secret" {
  command = plan
  variables {
    database_secret_version = "latest"
  }
  expect_failures = [var.database_secret_version]
}

run "daily_scan_at_seven_paris" {
  command = plan
  assert {
    condition = (
      google_cloud_scheduler_job.daily_scan.schedule == "0 7 * * *" &&
      google_cloud_scheduler_job.daily_scan.time_zone == "Europe/Paris" &&
      !google_cloud_scheduler_job.daily_scan.paused
    )
    error_message = "Run the scanner every day at 07:00 in Paris, including DST changes."
  }
  assert {
    condition = (
      length(google_cloud_scheduler_job.daily_scan.http_target[0].oidc_token) == 1 &&
      google_cloud_run_v2_service_iam_member.scheduled_scanner.role == "roles/run.invoker" &&
      google_cloud_scheduler_job.daily_scan.attempt_deadline == "900s" &&
      google_cloud_run_v2_service.scanner.template[0].timeout == "900s"
    )
    error_message = "Scheduler must authenticate to the scanner and wait for completion."
  }

}
