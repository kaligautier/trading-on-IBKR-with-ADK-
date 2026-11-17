mock_provider "google" {}

variables {
  project_id         = "preprod-deep-copy"
  caller_key_version = "1"
  image              = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/momentum-public-mcp@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}

run "public_stateless_front_door_private_readers" {
  command = plan
  assert {
    condition     = length(google_cloud_run_domain_mapping.mcp) == 0
    error_message = "Domain takeover requires explicit opt-in."
  }
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

run "transfer_only_public_mcp_domain" {
  command = plan
  variables {
    enable_domain_mapping = true
  }
  assert {
    condition     = length(google_cloud_run_domain_mapping.mcp) == 1 && google_cloud_run_domain_mapping.mcp[0].name == "mcp.deepcopy.fr"
    error_message = "Only the public MCP hostname may be transferred."
  }
  assert {
    condition     = google_cloud_run_domain_mapping.mcp[0].spec[0].route_name == google_cloud_run_v2_service.mcp.name && google_cloud_run_domain_mapping.mcp[0].spec[0].force_override
    error_message = "The cutover must target the new MCP service and replace the legacy mapping."
  }
  assert {
    condition     = google_cloud_run_domain_mapping.mcp[0].metadata[0].namespace == "preprod-deep-copy" && google_cloud_run_domain_mapping.mcp[0].location == "europe-west1"
    error_message = "The public domain must belong to the destination project and region."
  }
}

run "reject_domain_in_another_project" {
  command = plan
  variables {
    enable_domain_mapping = true
    project_id            = "other-project"
    image                 = "europe-west1-docker.pkg.dev/other-project/market-scanner/momentum-public-mcp@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
  expect_failures = [var.enable_domain_mapping]
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
