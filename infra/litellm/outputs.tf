output "ui_url" {
  value       = local.runtime_enabled ? "${local.base_url}/ui" : null
  description = "Protected by Google IAP; LiteLLM also requires its own admin login."
}

output "migration_job" {
  value = local.jobs_enabled ? google_cloud_run_v2_job.migrations[0].name : null
}

output "secret_ids" {
  value = { for name, secret in google_secret_manager_secret.credentials : name => secret.secret_id }
}

output "proxy_image" {
  value = local.proxy_image
}

output "gateway_url" {
  value       = local.runtime_enabled ? local.gateway_url : null
  description = "Internal-only inference endpoint; reachable from the attached VPC, not the internet."
}

output "network" {
  value = {
    network    = google_compute_network.private.name
    subnetwork = google_compute_subnetwork.run.name
  }
}
