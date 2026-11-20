mock_provider "google" {
  mock_data "google_project" {
    defaults = { number = "123456789012" }
  }
}
mock_provider "google-beta" {}

variables {
  project_id = "example-project"
}

run "typesafe_decision_model_uses_secret_reference" {
  command = plan
  variables {
    provider_secret_versions = { typesafe = "1" }
    provider_models          = { jev = { provider = "typesafe", model = "jev-latest" } }
  }
  assert {
    condition = (
      local.provider_models[0].model_name == "jev" &&
      local.provider_models[0].litellm_params.model == "typesafe/jev-latest" &&
      local.provider_models[0].litellm_params.api_key == "os.environ/TYPESAFE_API_KEY" &&
      contains(keys(local.proxy_provider_secret_env), "TYPESAFE_API_KEY")
    )
    error_message = "TypeSafe models must read TYPESAFE_API_KEY from a pinned Secret Manager version."
  }
}

run "reject_typesafe_without_key" {
  command = plan
  variables {
    provider_models = { jev = { provider = "typesafe", model = "jev-latest" } }
  }
  expect_failures = [var.provider_models]
}
