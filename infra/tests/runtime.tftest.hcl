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
  litellm_gateway = {
    url         = "https://gateway.example.run.app"
    key_secret  = "litellm-client-scanner"
    key_version = "2"
    network     = "private-services"
    subnetwork  = "cloud-run-egress"
  }
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
      [for env in google_cloud_run_v2_service.scanner.template[0].containers[0].env :
      env.value if env.name == "GOOGLE_GENAI_USE_VERTEXAI"] == ["false"] &&
      [for env in google_cloud_run_v2_service.scanner.template[0].containers[0].env :
      env.value if env.name == "LITELLM_API_BASE"] == [var.litellm_gateway.url]
    )
    error_message = "The scanner must route inference through LiteLLM."
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
      google_cloud_scheduler_job.daily_scan.attempt_deadline == "60s" &&
      google_cloud_run_v2_service.scanner.template[0].timeout == "900s"
    )
    error_message = "Scheduler must authenticate and wait only for job submission."
  }

}

run "independent_scan_job" {
  command = plan
  assert {
    condition = (
      google_cloud_run_v2_job.daily_scan.template[0].task_count == 1 &&
      google_cloud_run_v2_job.daily_scan.template[0].parallelism == 1 &&
      google_cloud_run_v2_job.daily_scan.template[0].template[0].max_retries == 0 &&
      google_cloud_run_v2_job.daily_scan.template[0].template[0].timeout == "900s"
    )
    error_message = "One task owns the full scan; no automatic duplicate retry."
  }
  assert {
    condition = (
      google_cloud_run_v2_job_iam_member.dispatcher.role == "roles/run.invoker" &&
      google_cloud_run_v2_job.daily_scan.template[0].template[0].containers[0].command == tolist(["/app/.venv/bin/python"]) &&
      google_cloud_run_v2_job.daily_scan.template[0].template[0].containers[0].args == tolist(["-m", "app.jobs.daily_scan"])
    )
    error_message = "The dispatcher invokes the job; the job executes ADK without starting the HTTP server."
  }
}

run "gateway_for_api_and_worker" {
  command = plan
  assert {
    condition = alltrue([
      for envs in [
        google_cloud_run_v2_service.scanner.template[0].containers[0].env,
        google_cloud_run_v2_job.daily_scan.template[0].template[0].containers[0].env
        ] : (
        [for env in envs : env.value if env.name == "LITELLM_API_BASE"] == [var.litellm_gateway.url] &&
        [for env in envs : env.value_source[0].secret_key_ref[0].version if env.name == "LITELLM_API_KEY"] == ["2"] &&
        [for env in envs : env.value_source[0].secret_key_ref[0].secret if env.name == "LITELLM_API_KEY"] == [var.litellm_gateway.key_secret]
      )
    ])
    error_message = "API and scheduled worker must share the gateway and pinned virtual-key secret."
  }
  assert {
    condition = alltrue([
      for vpc in [
        google_cloud_run_v2_service.scanner.template[0].vpc_access[0],
        google_cloud_run_v2_job.daily_scan.template[0].template[0].vpc_access[0]
        ] : (
        vpc.egress == "PRIVATE_RANGES_ONLY" &&
        vpc.network_interfaces[0].network == var.litellm_gateway.network &&
        vpc.network_interfaces[0].subnetwork == var.litellm_gateway.subnetwork
      )
    ])
    error_message = "Both execution paths need the gateway VPC."
  }
}

run "reject_mutable_gateway_key" {
  command = plan
  variables {
    litellm_gateway = {
      url         = "https://gateway.example.run.app"
      key_secret  = "litellm-client-scanner"
      key_version = "latest"
      network     = "private-services"
      subnetwork  = "cloud-run-egress"
    }
  }
  expect_failures = [var.litellm_gateway]
}
