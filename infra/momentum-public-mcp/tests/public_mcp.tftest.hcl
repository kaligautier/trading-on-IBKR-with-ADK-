mock_provider "google" {}

variables {
  project_id         = "preprod-deep-copy"
  caller_key_version = "1"
  image              = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/momentum-public-mcp@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}

run "public_stateless_front_door_private_readers" {
  command = plan
  assert {
    condition     = google_cloud_run_v2_service.mcp.invoker_iam_disabled && google_cloud_run_v2_service.mcp.ingress == "INGRESS_TRAFFIC_ALL"
    error_message = "Only the MCP front door must be publicly reachable."
  }
  assert {
    condition     = !google_cloud_run_v2_service.mcp.template[0].session_affinity
    error_message = "No sticky sessions for stateless MCP."
  }
  assert {
    condition     = toset(keys(google_cloud_run_v2_service_iam_member.reader)) == toset(["momentum-api", "market-scanner-api"])
    error_message = "MCP can invoke only the two consultation readers, never ADK execution."
  }
  assert {
    condition     = google_cloud_run_v2_service.mcp.template[0].scaling[0].max_instance_count == 3
    error_message = "Public scaling must remain bounded."
  }
}

run "reject_mutable_release" {
  command = plan
  variables {
    image = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/momentum-public-mcp:latest"
  }
  expect_failures = [var.image]
}

run "reject_floating_secret" {
  command = plan
  variables {
    caller_key_version = "latest"
  }
  expect_failures = [var.caller_key_version]
}

run "reject_invalid_sampling" {
  command = plan
  variables {
    log_success_sample_rate = 1.1
    log_slow_request_ms     = 0
  }
  expect_failures = [var.log_success_sample_rate, var.log_slow_request_ms]
}
