mock_provider "google" {
  mock_data "google_project" {
    defaults = { number = "123456789012" }
  }
}
mock_provider "google-beta" {}

variables {
  project_id = "example-project"
}

run "foundation_has_no_running_workloads" {
  command = plan
  assert {
    condition     = length(google_cloud_run_v2_service.litellm) == 0 && length(google_cloud_run_v2_job.migrations) == 0
    error_message = "Foundation must be deployable before secrets and database are available."
  }
}

run "migration_stage_has_no_web_service" {
  command = plan
  variables {
    stage = "migrations"
    secret_versions = {
      database-url = "1"
      master-key   = "1"
      salt-key     = "1"
      ui-password  = "1"
    }
  }
  assert {
    condition     = length(google_cloud_run_v2_service.litellm) == 0 && length(google_cloud_run_v2_job.migrations) == 1
    error_message = "Migrations must be runnable before the first service is created."
  }
  assert {
    condition     = toset(keys(google_secret_manager_secret_iam_member.migrations)) == toset(["database-url", "database-ca"])
    error_message = "Migration identity must not read admin credentials or the encryption key."
  }
}

run "service_requires_iap_and_keeps_native_auth" {
  command = plan
  variables {
    stage       = "service"
    iap_members = ["user:owner@example.com"]
    secret_versions = {
      database-url = "2"
      master-key   = "3"
      salt-key     = "4"
      ui-password  = "5"
      database-ca  = "6"
    }
  }
  assert {
    condition = (
      google_cloud_run_v2_service.litellm[0].iap_enabled &&
      !google_cloud_run_v2_service.litellm[0].invoker_iam_disabled &&
      google_cloud_run_v2_service_iam_member.iap_invoker[0].role == "roles/run.invoker" &&
      google_iap_web_cloud_run_service_iam_member.users["user:owner@example.com"].role == "roles/iap.httpsResourceAccessor"
    )
    error_message = "All ingress must require IAP and retain the Cloud Run invoker check."
  }
  assert {
    condition = (
      [for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env : env.value if env.name == "PROXY_BASE_URL"] ==
      ["https://litellm-123456789012.europe-west1.run.app"]
    )
    error_message = "Login redirects must use the external HTTPS origin, not the container's HTTP URL."
  }
  assert {
    condition = alltrue([
      for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env :
      env.name != "GOOGLE_API_KEY" && env.name != "GOOGLE_APPLICATION_CREDENTIALS" &&
      (!contains(keys(local.runtime_secrets), env.name) || (env.value == null && length(env.value_source) == 1))
    ])
    error_message = "Credentials must use secret references and Vertex must use attached identity."
  }
  assert {
    condition = (
      [for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env : env.value if env.name == "DISABLE_SCHEMA_UPDATE"] == ["true"] &&
      google_cloud_run_v2_service.litellm[0].template[0].scaling[0].max_instance_count == 1 &&
      yamldecode(local.proxy_config).general_settings.database_connection_pool_limit == 2 &&
      !yamldecode(local.proxy_config).general_settings.allow_requests_on_db_unavailable
    )
    error_message = "Keep migrations out of web startup, bound the DB pool and fail closed on DB outages."
  }
  assert {
    condition = (
      length(google_cloud_run_v2_service.litellm[0].template[0].volumes) == 2 &&
      length(google_cloud_run_v2_job.migrations[0].template[0].template[0].volumes) == 1
    )
    error_message = "Mount the PostgreSQL CA in both the proxy and migration job."
  }
}

run "reject_public_access" {
  command = plan
  variables {
    iap_members = ["allUsers"]
  }
  expect_failures = [var.iap_members]
}

run "reject_no_service_users" {
  command = plan
  variables {
    stage = "service"
    secret_versions = {
      database-url = "1"
      master-key   = "1"
      salt-key     = "1"
      ui-password  = "1"
    }
  }
  expect_failures = [var.iap_members]
}

run "reject_missing_credentials" {
  command = plan
  variables {
    stage = "migrations"
  }
  expect_failures = [var.secret_versions]
}

run "reject_mutable_secrets" {
  command = plan
  variables {
    secret_versions = { database-url = "latest" }
  }
  expect_failures = [var.secret_versions]
}

run "reject_mutable_image" {
  command = plan
  variables {
    proxy_digest = "latest"
  }
  expect_failures = [var.proxy_digest]
}

run "providers_are_inactive_without_credentials" {
  command = plan
  assert {
    condition = (
      length(google_secret_manager_secret.provider) == 3 &&
      length(google_secret_manager_secret_iam_member.provider) == 0 &&
      length(yamldecode(local.proxy_config).model_list) == 1
    )
    error_message = "Preparing provider secret containers must not grant access or expose unconfigured models."
  }
}

run "providers_use_secret_references_and_preserve_vertex" {
  command = plan
  variables {
    stage                    = "service"
    iap_members              = ["user:owner@example.com"]
    secret_versions          = { database-url = "1", master-key = "1", salt-key = "1", ui-password = "1" }
    provider_secret_versions = { openai = "2", anthropic = "3", gemini = "4" }
    provider_models = {
      openai-chat    = { provider = "openai", model = "test-model" }
      anthropic-chat = { provider = "anthropic", model = "test-model" }
      gemini-chat    = { provider = "gemini", model = "test-model" }
    }
  }
  assert {
    condition = (
      length(yamldecode(local.proxy_config).model_list) == 4 &&
      alltrue([for model in local.provider_models : startswith(model.litellm_params.api_key, "os.environ/")]) &&
      alltrue([for env in google_cloud_run_v2_service.litellm[0].template[0].containers[0].env :
        env.value == null && length(env.value_source) == 1
        if contains(values(local.provider_environment), env.name)
      ]) &&
      length(google_secret_manager_secret_iam_member.provider) == 3 &&
      toset(keys(google_secret_manager_secret_iam_member.migrations)) == toset(["database-url", "database-ca"])
    )
    error_message = "Provider credentials must resolve via runtime-only secrets while preserving Vertex and migration isolation."
  }
  assert {
    condition = (
      !yamldecode(local.proxy_config).general_settings.store_prompts_in_spend_logs &&
      yamldecode(local.proxy_config).litellm_settings.turn_off_message_logging &&
      yamldecode(local.proxy_config).litellm_settings.user_url_validation &&
      yamldecode(local.proxy_config).router_settings.retry_policy.AuthenticationErrorRetries == 0 &&
      yamldecode(local.proxy_config).router_settings.timeout < 600
    )
    error_message = "Provider requests must retain privacy, URL validation, bounded timeouts and no authentication retries."
  }
}

run "reject_provider_without_key" {
  command = plan
  variables {
    provider_models = { chat = { provider = "openai", model = "test-model" } }
  }
  expect_failures = [var.provider_models]
}

run "reject_provider_wildcard" {
  command = plan
  variables {
    provider_secret_versions = { openai = "1" }
    provider_models          = { chat = { provider = "openai", model = "*" } }
  }
  expect_failures = [var.provider_models]
}

run "reject_mutable_provider_secret" {
  command = plan
  variables {
    provider_secret_versions = { openai = "latest" }
  }
  expect_failures = [var.provider_secret_versions]
}

run "additional_vertex_models_share_attached_identity" {
  command = plan
  variables {
    additional_vertex_models = ["gemini-3.7-flash", "gemini-3.5-flash-lite"]
  }
  assert {
    condition = (
      length(yamldecode(local.proxy_config).model_list) == 3 &&
      alltrue([for model in yamldecode(local.proxy_config).model_list :
        model.litellm_params.vertex_location == var.vertex_location &&
        model.litellm_params.vertex_project == var.project_id &&
        !contains(keys(model.litellm_params), "api_key")
      ])
    )
    error_message = "Every Vertex model must use the selected location and attached project identity."
  }
}

run "reject_duplicate_vertex_model" {
  command = plan
  variables {
    additional_vertex_models = ["gemini-3.8-flash"]
  }
  expect_failures = [var.additional_vertex_models]
}

run "application_clients_are_scoped" {
  command = plan
  variables {
    iap_members = ["user:owner@example.com"]
    stage       = "service"
    secret_versions = {
      database-url = "1"
      database-ca  = "1"
      master-key   = "1"
      salt-key     = "1"
      ui-password  = "1"
    }
    client_service_accounts = {
      market-scanner-adk = "market-scanner-adk@example-project.iam.gserviceaccount.com"
    }
    client_operator_members = ["user:owner@example.com"]
  }
  assert {
    condition = (
      google_service_account_iam_member.client_signer["market-scanner-adk"].service_account_id == "projects/example-project/serviceAccounts/market-scanner-adk@example-project.iam.gserviceaccount.com" &&
      google_service_account_iam_member.client_signer["market-scanner-adk"].member == "serviceAccount:market-scanner-adk@example-project.iam.gserviceaccount.com" &&
      google_service_account_iam_member.client_signer["market-scanner-adk"].role == "roles/iam.serviceAccountTokenCreator"
    )
    error_message = "The runtime can sign only as its own service account."
  }
  assert {
    condition = (
      google_iap_web_cloud_run_service_iam_member.clients["market-scanner-adk"].role == "roles/iap.httpsResourceAccessor" &&
      google_secret_manager_secret.client_key["market-scanner-adk"].secret_id == "litellm-client-market-scanner-adk" &&
      google_secret_manager_secret_iam_member.client_key["market-scanner-adk"].member == "serviceAccount:market-scanner-adk@example-project.iam.gserviceaccount.com"
    )
    error_message = "The client must use IAP and its dedicated credential, never the master key."
  }
}

run "reject_foreign_client_identity" {
  command = plan
  variables {
    client_service_accounts = { scanner = "scanner@another-project.iam.gserviceaccount.com" }
  }
  expect_failures = [var.client_service_accounts]
}

run "gateway_is_internal_only_without_iap" {
  command = plan
  variables {
    stage       = "service"
    iap_members = ["user:owner@example.com"]
    secret_versions = {
      database-url = "2"
      master-key   = "3"
      salt-key     = "4"
      ui-password  = "5"
    }
  }
  assert {
    condition = (
      google_cloud_run_v2_service.gateway[0].ingress == "INGRESS_TRAFFIC_INTERNAL_ONLY" &&
      !google_cloud_run_v2_service.gateway[0].iap_enabled &&
      google_cloud_run_v2_service.litellm[0].iap_enabled &&
      google_compute_subnetwork.run.private_ip_google_access
    )
    error_message = "Only the admin front is IAP-exposed; the gateway must be VPC-internal."
  }
}
