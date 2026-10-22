resource "google_service_account" "scanner" {
  project      = var.project_id
  account_id   = "market-scanner-adk"
  display_name = "Market Scanner runtime"
}

resource "google_secret_manager_secret_iam_member" "database" {
  project   = var.project_id
  secret_id = "market-scanner-database-url"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.scanner.email}"
}

resource "google_cloud_run_v2_service_iam_member" "invoker" {
  for_each = var.invoker_members
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.scanner.name
  role     = "roles/run.invoker"
  member   = each.value
}
