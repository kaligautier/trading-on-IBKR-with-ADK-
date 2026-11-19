mock_provider "google" {
  mock_data "google_project" {
    defaults = { number = "123456789012" }
  }
}
mock_provider "archive" {
  mock_data "archive_file" {
    defaults = { output_md5 = "d41d8cd98f00b204e9800998ecf8427e", output_path = "/tmp/function.zip" }
  }
}

variables {
  project_id         = "preprod-deep-copy"
  billing_account_id = "ABCDEF-012345-6789AB"
}

run "caps_the_project_and_disables_vertex" {
  command = plan
  assert {
    condition     = google_billing_budget.guard.budget_filter[0].projects == toset(["projects/123456789012"])
    error_message = "The budget must be scoped to the target project only."
  }
  assert {
    condition     = google_billing_budget.guard.amount[0].specified_amount[0].units == "50" && google_billing_budget.guard.amount[0].specified_amount[0].currency_code == "EUR"
    error_message = "Default budget is 50 EUR."
  }
  assert {
    condition     = google_cloudfunctions2_function.guard.service_config[0].environment_variables.SERVICES_TO_DISABLE == "aiplatform.googleapis.com"
    error_message = "Only Vertex AI is disabled by default."
  }
}

run "function_is_private_and_least_privilege" {
  command = plan
  assert {
    condition     = google_cloudfunctions2_function.guard.service_config[0].ingress_settings == "ALLOW_INTERNAL_ONLY"
    error_message = "The kill switch must not be callable from the internet."
  }
  assert {
    condition     = toset(google_project_iam_custom_role.service_disabler.permissions) == toset(["serviceusage.services.disable", "serviceusage.services.get", "serviceusage.services.use", "serviceusage.operations.get"])
    error_message = "The function role must only allow disabling services and using the project (needed by the Eventarc trigger)."
  }
}

run "rejects_bad_inputs" {
  command = plan
  variables {
    billing_account_id = "my-billing-account"
  }
  expect_failures = [var.billing_account_id]
}

run "rejects_non_positive_budget" {
  command = plan
  variables {
    budget_amount = 0
  }
  expect_failures = [var.budget_amount]
}
