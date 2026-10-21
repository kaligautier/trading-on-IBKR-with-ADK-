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
