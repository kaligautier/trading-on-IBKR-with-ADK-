mock_provider "google" {
  mock_data "google_cloud_run_v2_service" {
    defaults = {
      name = "market-scanner-api"
      uri  = "https://market-scanner-api-test.europe-west1.run.app"
    }
  }
}

variables {
  project_id = "preprod-deep-copy"
  image      = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/deepcopy-front@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
}

run "stage_without_domain_takeover" {
  command = plan
  assert {
    condition     = length(google_cloud_run_domain_mapping.frontend) == 0
    error_message = "Staging must leave the live domains in Demo ADK."
  }
  assert {
    condition     = google_cloud_run_v2_service.frontend.invoker_iam_disabled && google_cloud_run_v2_service.frontend.deletion_protection
    error_message = "The landing must be public and protected from accidental deletion."
  }
  assert {
    condition     = google_cloud_run_v2_service_iam_member.reader_invoker.name == "market-scanner-api" && google_cloud_run_v2_service_iam_member.reader_invoker.role == "roles/run.invoker"
    error_message = "Grant frontend invocation only on the private reader."
  }
  assert {
    condition = alltrue([
      for env in google_cloud_run_v2_service.frontend.template[0].containers[0].env :
      env.name == "MARKET_SCANNER_API_USE_IAM" ? env.value == "true" : env.value == "https://market-scanner-api-test.europe-west1.run.app"
    ])
    error_message = "Always call the destination reader using Cloud Run IAM."
  }
}

run "explicit_frontend_cutover" {
  command = plan
  variables {
    enable_domain_mappings = true
  }
  assert {
    condition     = toset(keys(google_cloud_run_domain_mapping.frontend)) == toset(["deepcopy.fr", "www.deepcopy.fr"])
    error_message = "Transfer only the frontend domains; never take over mcp.deepcopy.fr."
  }
  assert {
    condition     = alltrue([for mapping in google_cloud_run_domain_mapping.frontend : mapping.spec[0].force_override && mapping.metadata[0].namespace == "preprod-deep-copy"])
    error_message = "The reviewed cutover must transfer the mappings to DeepCopy."
  }
}

run "reject_demo_adk_image" {
  command = plan
  variables {
    image = "europe-west1-docker.pkg.dev/gen-lang-client-0690499141/deepcopy/front@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
  expect_failures = [var.image]
}

run "reject_mutable_image" {
  command = plan
  variables {
    image = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/deepcopy-front:latest"
  }
  expect_failures = [var.image]
}

run "reject_source_project" {
  command = plan
  variables {
    project_id = "gen-lang-client-0690499141"
    image      = "europe-west1-docker.pkg.dev/gen-lang-client-0690499141/market-scanner/deepcopy-front@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  }
  expect_failures = [var.project_id]
}
