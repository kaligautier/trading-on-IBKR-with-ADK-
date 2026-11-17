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
    condition = (
      google_cloud_run_v2_job.analysis[0].template[0].template[0].volumes[0].secret[0].items[0].version == var.database_ca_version &&
      google_cloud_run_v2_job.analysis[0].template[0].template[0].containers[0].volume_mounts[0].mount_path == "/etc/database" &&
      [for env in google_cloud_run_v2_job.analysis[0].template[0].template[0].containers[0].env : env.value if env.name == "DATABASE_CA_FILE"] == ["/etc/database/ca.pem"]
    )
    error_message = "Momentum must use the pinned database CA for both pools."
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
    condition = toset([for env in google_cloud_run_v2_job.analysis[0].template[0].template[0].containers[0].env : env.name]) == toset([
      "DATABASE_CA_FILE", "LITELLM_API_BASE", "MOMENTUM_QUICK_MODEL", "MOMENTUM_DEEP_MODEL",
      "LITELLM_API_KEY", "MOMENTUM_SESSION_DATABASE_URL", "MOMENTUM_RESULT_DATABASE_URL"
    ])
    error_message = "Only the CA path, explicit gateway, models and three credentials belong in runtime."
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

run "reject_gateway_empty_label" {
  command = plan
  variables { gateway_url = "https://gateway..example" }
  expect_failures = [var.gateway_url]
}

run "reject_gateway_leading_hyphen" {
  command = plan
  variables { gateway_url = "https://-gateway.example" }
  expect_failures = [var.gateway_url]
}

run "reject_gateway_trailing_hyphen" {
  command = plan
  variables { gateway_url = "https://gateway-.example" }
  expect_failures = [var.gateway_url]
}

run "reject_gateway_long_label" {
  command = plan
  variables { gateway_url = "https://${join("", [for j in range(64) : "a"])}.example" }
  expect_failures = [var.gateway_url]
}

run "reject_gateway_long_hostname" {
  command = plan
  variables { gateway_url = "https://${join(".", [for i in range(4) : join("", [for j in range(63) : "a"])])}" }
  expect_failures = [var.gateway_url]
}

run "accept_gateway_dns_boundaries" {
  command = plan
  variables { gateway_url = "https://${join(".", concat([for i in range(3) : join("", [for j in range(63) : "a"])], [join("", [for j in range(61) : "b"])]))}/" }
}
