mock_provider "google" {}
mock_provider "google-beta" {}
variables { project_id = "example-project" }

run "patched_release_requires_immutable_images" {
  command = plan
  variables {
    release_images = {
      proxy      = "europe-west1-docker.pkg.dev/example-project/releases/litellm:latest"
      migrations = "europe-west1-docker.pkg.dev/example-project/releases/migrations:latest"
    }
  }
  expect_failures = [var.release_images]
}

run "patched_release_reaches_both_services_and_migrations" {
  command = plan
  variables {
    stage       = "service"
    iap_members = ["user:owner@example.com"]
    secret_versions = {
      database-url = "1"
      master-key   = "1"
      salt-key     = "1"
      ui-password  = "1"
    }
    release_images = {
      proxy      = "europe-west1-docker.pkg.dev/example-project/releases/litellm@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      migrations = "europe-west1-docker.pkg.dev/example-project/releases/migrations@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    }
  }
  assert {
    condition = (
      google_cloud_run_v2_service.litellm[0].template[0].containers[0].image == var.release_images.proxy &&
      google_cloud_run_v2_job.migrations[0].template[0].template[0].containers[0].image == var.release_images.migrations &&
      google_cloud_run_v2_service.gateway[0].template[0].containers[1].image == var.release_images.proxy
    )
    error_message = "The patched release must replace the runtime and migration image pair."
  }
}
