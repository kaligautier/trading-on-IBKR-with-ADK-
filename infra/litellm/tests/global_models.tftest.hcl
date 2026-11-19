mock_provider "google" {
  mock_data "google_project" {
    defaults = { number = "123456789012" }
  }
}
mock_provider "google-beta" {}

variables {
  project_id = "example-project"
}

run "global_vertex_models_use_global_location_only" {
  command = plan
  variables {
    additional_vertex_models = ["gemini-4-argon", "gemini-4-other"]
    global_vertex_models     = ["gemini-4-argon"]
  }
  assert {
    condition = (
      [for m in yamldecode(local.proxy_config).model_list : m.litellm_params.vertex_location if m.model_name == "gemini-4-argon"][0] == "global" &&
      [for m in yamldecode(local.proxy_config).model_list : m.litellm_params.vertex_location if m.model_name == "gemini-4-other"][0] == var.vertex_location
    )
    error_message = "Only models listed in global_vertex_models may use the global Vertex endpoint."
  }
}

run "reject_global_model_not_exposed" {
  command = plan
  variables { global_vertex_models = ["gemini-4-argon"] }
  expect_failures = [var.global_vertex_models]
}
