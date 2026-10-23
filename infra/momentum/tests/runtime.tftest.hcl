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
