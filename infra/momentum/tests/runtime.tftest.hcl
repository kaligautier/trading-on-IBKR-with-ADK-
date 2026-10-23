mock_provider "google" {}
variables {
  project_id  = "preprod-deep-copy"
  gateway_url = "https://gateway.example"
}
run "foundation_has_no_execution" {
  command = plan
  assert {
    condition     = length(google_cloud_run_v2_job.analysis) == 0
    error_message = "Foundation must not launch an unbuilt image."
  }
}
run "bounded_private_worker" {
  command = plan
  variables {
    image = "europe-west1-docker.pkg.dev/preprod-deep-copy/momentum/worker@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
  assert {
    condition     = google_cloud_run_v2_job.analysis[0].template[0].parallelism == 1 && google_cloud_run_v2_job.analysis[0].template[0].template[0].max_retries == 0
    error_message = "Bound concurrency and disable automatic paid retries."
  }
  assert {
    condition     = google_cloud_run_v2_job.analysis[0].template[0].template[0].vpc_access[0].egress == "PRIVATE_RANGES_ONLY"
    error_message = "Use the private gateway network."
  }
  assert {
    condition     = length(google_cloud_run_v2_job.analysis[0].template[0].template[0].containers[0].env) == 6
    error_message = "Only explicit gateway, models and three credentials belong in runtime."
  }
}

run "reject_secret_aliases" {
  command = plan
  variables {
    llm_key_version          = "latest"
    session_database_version = "active"
    result_database_version  = "0"
  }
  expect_failures = [var.llm_key_version, var.session_database_version, var.result_database_version]
}

run "database_credentials_are_recoverable" {
  command = plan
  assert {
    condition = alltrue([for secret in google_secret_manager_secret.database :
      secret.deletion_protection && secret.version_destroy_ttl == "2592000s"
    ])
    error_message = "Protect both database secrets and delay destruction of individual versions by 30 days."
  }
}
run "accept_https_root_with_trailing_slash" {
  command = plan
  variables { gateway_url = "https://gateway.example/" }
}

run "reject_gateway_http" {
  command = plan
  variables { gateway_url = "http://gateway.example" }
  expect_failures = [var.gateway_url]
}

run "reject_gateway_credentials" {
  command = plan
  variables { gateway_url = "https://user:pass@gateway.example" }
  expect_failures = [var.gateway_url]
}

run "reject_gateway_path" {
  command = plan
  variables { gateway_url = "https://gateway.example/v1" }
  expect_failures = [var.gateway_url]
}

run "reject_gateway_query" {
  command = plan
  variables { gateway_url = "https://gateway.example?key=test" }
  expect_failures = [var.gateway_url]
}

run "reject_gateway_fragment" {
  command = plan
  variables { gateway_url = "https://gateway.example#test" }
  expect_failures = [var.gateway_url]
}

run "reject_gateway_empty" {
  command = plan
  variables { gateway_url = "" }
  expect_failures = [var.gateway_url]
}

run "reject_gateway_missing_host" {
  command = plan
  variables { gateway_url = "https://" }
  expect_failures = [var.gateway_url]
}
