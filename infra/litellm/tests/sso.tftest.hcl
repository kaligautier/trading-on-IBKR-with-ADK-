mock_provider "google" {
  mock_data "google_project" {
    defaults = { number = "123456789012" }
  }
}
mock_provider "google-beta" {}

variables {
  project_id  = "example-project"
  stage       = "service"
  iap_members = ["user:owner@example.com"]
  secret_versions = {
    database-url = "1"
    master-key   = "1"
    salt-key     = "1"
    ui-password  = "1"
  }
}

run "sso_is_opt_in" {
  command = plan
  assert {
    condition = (
      length(google_secret_manager_secret_iam_member.google_sso) == 0 &&
      alltrue([for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env :
        !contains(["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "PROXY_ADMIN_ID"], env.name)
      ])
    )
    error_message = "Preparing the secret container must not change the current admin login."
  }
}

run "google_sso_is_scoped_to_admin_with_pinned_secret_and_iap" {
  command = plan
  variables {
    google_sso = {
      client_id             = "123456789012-example.apps.googleusercontent.com"
      client_secret_version = "3"
      admin_id              = "b69789fa-bb16-41b3-bd9e-19bb3a511070"
    }
  }
  assert {
    condition = (
      [for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env : env.value if env.name == "GOOGLE_CLIENT_ID"] == [var.google_sso.client_id] &&
      [for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env : env.value if env.name == "PROXY_ADMIN_ID"] == [var.google_sso.admin_id] &&
      one([for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env : env if env.name == "GOOGLE_CLIENT_SECRET"]).value == null &&
      one([for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env : env if env.name == "GOOGLE_CLIENT_SECRET"]).value_source[0].secret_key_ref[0].secret == "litellm-google-client-secret" &&
      one([for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env : env if env.name == "GOOGLE_CLIENT_SECRET"]).value_source[0].secret_key_ref[0].version == "3" &&
      google_secret_manager_secret_iam_member.google_sso[0].role == "roles/secretmanager.secretAccessor"
    )
    error_message = "Google SSO must use the selected administrator and a pinned Secret Manager reference, never a plaintext secret."
  }
  assert {
    condition = (
      google_cloud_run_v2_service.litellm[0].iap_enabled &&
      !google_cloud_run_v2_service.litellm[0].invoker_iam_disabled &&
      contains([for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env : env.name], "UI_PASSWORD") &&
      !try(yamldecode(local.proxy_config).general_settings.disable_env_credential_login, false) &&
      output.google_sso_callback_url == "https://litellm-123456789012.europe-west1.run.app/sso/callback"
    )
    error_message = "Keep IAP, the existing fallback login and the exact external HTTPS callback."
  }
  assert {
    condition = alltrue(flatten([
      for container in google_cloud_run_v2_service.gateway[0].template[0].containers : [
        for env in container.env : !contains(["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "PROXY_ADMIN_ID"], env.name)
      ]
    ]))
    error_message = "Inference gateway containers must not receive UI SSO configuration."
  }
}

run "sso_can_bootstrap_before_the_admin_id_is_known" {
  command = plan
  variables {
    google_sso = {
      client_id             = "123456789012-example.apps.googleusercontent.com"
      client_secret_version = "1"
    }
  }
  assert {
    condition = (
      contains([for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env : env.name], "GOOGLE_CLIENT_ID") &&
      contains([for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env : env.name], "UI_PASSWORD") &&
      !contains([for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env : env.name], "PROXY_ADMIN_ID")
    )
    error_message = "Allow the first Google login to reveal the LiteLLM User ID while keeping the fallback admin available."
  }
}

run "reject_mutable_sso_secret" {
  command = plan
  variables {
    google_sso = {
      client_id             = "123456789012-example.apps.googleusercontent.com"
      client_secret_version = "latest"
      admin_id              = "123456789012345678901"
    }
  }
  expect_failures = [var.google_sso]
}

run "reject_blank_admin_id" {
  command = plan
  variables {
    google_sso = {
      client_id             = "123456789012-example.apps.googleusercontent.com"
      client_secret_version = "1"
      admin_id              = " "
    }
  }
  expect_failures = [var.google_sso]
}
