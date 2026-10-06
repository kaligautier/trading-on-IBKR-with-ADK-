mock_provider "google" {}

variables {
  project_id = "preprod-deep-copy"
}

run "isolated_foundation" {
  command = plan
  assert {
    condition = (
      google_storage_bucket.terraform_state.name == "preprod-deep-copy-tfstate" &&
      google_storage_bucket.terraform_state.public_access_prevention == "enforced" &&
      google_storage_bucket.terraform_state.uniform_bucket_level_access &&
      google_storage_bucket.terraform_state.versioning[0].enabled &&
      !google_storage_bucket.terraform_state.force_destroy
    )
    error_message = "Keep the dedicated Terraform state private and recoverable."
  }
  assert {
    condition     = alltrue([for api in google_project_service.apis : !api.disable_on_destroy])
    error_message = "Removing this stack must not disable shared project APIs."
  }
}
