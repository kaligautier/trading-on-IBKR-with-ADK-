terraform {
  required_providers { google = { source = "hashicorp/google", version = "~> 7.46" } }
}
resource "google_secret_manager_secret" "momentum_key" {
  count     = 1
  project   = "example-project"
  secret_id = "litellm-client-momentum"
  replication {
    auto {}
  }
  lifecycle { prevent_destroy = true }
}
output "secret_id" { value = google_secret_manager_secret.momentum_key[0].id }
