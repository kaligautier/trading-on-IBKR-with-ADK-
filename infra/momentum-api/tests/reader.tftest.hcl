mock_provider "google" {}

variables {
  project_id              = "contract-project"
  region                  = "europe-west1"
  image                   = "europe-west1-docker.pkg.dev/contract-project/market-scanner/momentum-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  database_secret_version = "1"
  ca_secret_version       = "1"
  invoker_members         = ["serviceAccount:future-mcp@contract-project.iam.gserviceaccount.com"]
}

run "private_bounded_reader" {
  command = plan
  assert {
    condition     = !google_cloud_run_v2_service.reader.invoker_iam_disabled
    error_message = "Cloud Run IAM must verify invokers."
  }
  assert {
    condition     = google_cloud_run_v2_service.reader.template[0].scaling[0].max_instance_count == 1
    error_message = "Bound the pool's per-revision instance count."
  }
  assert {
    condition     = google_cloud_run_v2_service.reader.template[0].max_instance_request_concurrency == 20
    error_message = "Bound concurrency and pool wait."
  }
  assert {
    condition     = length(google_secret_manager_secret_iam_member.reader) == 2
    error_message = "Reader only needs its database URL and CA."
  }
  assert {
    condition     = length(google_cloud_run_v2_service_iam_member.invoker) == 1
    error_message = "Only explicit invokers may read the shared catalogue."
  }
  assert {
    condition     = google_cloud_run_v2_service.reader.deletion_protection
    error_message = "Protect this independently managed service."
  }
}

run "no_anonymous_invoker" {
  command = plan
  variables {
    invoker_members = ["allUsers"]
  }
  expect_failures = [var.invoker_members]
}

run "no_authenticated_public_invoker" {
  command = plan
  variables {
    invoker_members = ["allAuthenticatedUsers"]
  }
  expect_failures = [var.invoker_members]
}

run "no_mutable_image" {
  command = plan
  variables {
    image = "europe-west1-docker.pkg.dev/contract-project/market-scanner/momentum-api:latest"
  }
  expect_failures = [var.image]
}

run "no_latest_database_secret" {
  command = plan
  variables {
    database_secret_version = "latest"
  }
  expect_failures = [var.database_secret_version]
}

run "no_latest_ca_secret" {
  command = plan
  variables {
    ca_secret_version = "latest"
  }
  expect_failures = [var.ca_secret_version]
}
