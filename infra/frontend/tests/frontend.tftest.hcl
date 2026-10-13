mock_provider "google" {}

variables {
  project_id = "frontend-test-project"
  image      = "europe-west1-docker.pkg.dev/frontend-test-project/market-scanner/market-scanner-front@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}

run "public_frontend_private_reader_boundary" {
  command = plan
  assert {
    condition     = google_cloud_run_v2_service.frontend.invoker_iam_disabled && google_cloud_run_v2_service.frontend.ingress == "INGRESS_TRAFFIC_ALL"
    error_message = "Visitors must be able to access the frontend without a login."
  }
  assert {
    condition     = google_cloud_run_v2_service_iam_member.reader_invoker.role == "roles/run.invoker" && startswith(google_cloud_run_v2_service_iam_member.reader_invoker.member, "serviceAccount:")
    error_message = "Only the frontend identity may receive this scoped reader grant."
  }
  assert {
    condition     = google_cloud_run_v2_service.frontend.template[0].scaling[0].min_instance_count == 0 && google_cloud_run_v2_service.frontend.template[0].scaling[0].max_instance_count == 1
    error_message = "Keep instances bounded and permit scale to zero."
  }
  assert {
    condition     = one([for env in google_cloud_run_v2_service.frontend.template[0].containers[0].env : env.value if env.name == "MARKET_SCANNER_API_USE_IAM"]) == "true"
    error_message = "Production reader requests must use workload identity."
  }
}

run "reject_mutable_image" {
  command = plan
  variables {
    image = "europe-west1-docker.pkg.dev/frontend-test-project/market-scanner/market-scanner-front:latest"
  }
  expect_failures = [var.image]
}
