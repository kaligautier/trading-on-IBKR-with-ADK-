resource "google_service_account" "scanner_scheduler" {
  project      = var.project_id
  account_id   = "market-scanner-scheduler"
  display_name = "Market Scanner schedule"
}

resource "google_cloud_run_v2_service_iam_member" "scheduled_scanner" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.scanner.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scanner_scheduler.email}"
}

resource "google_cloud_scheduler_job" "daily_scan" {
  project          = var.project_id
  region           = var.region
  name             = "market-scanner-daily-0700"
  description      = "Submit the daily ADK scan job at 07:00 Paris time."
  schedule         = "0 7 * * *"
  time_zone        = "Europe/Paris"
  attempt_deadline = "60s"
  paused           = false

  # A retry could submit another execution after an interrupted acknowledgement.
  retry_config {
    retry_count          = 0
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 5
  }

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.scanner.uri}/internal/daily-scan"
    headers     = { "Content-Type" = "application/json" }
    body        = base64encode("{}")
    oidc_token {
      service_account_email = google_service_account.scanner_scheduler.email
      audience              = google_cloud_run_v2_service.scanner.uri
    }
  }
  depends_on = [google_cloud_run_v2_service_iam_member.scheduled_scanner]
}

output "daily_scan_schedule" {
  value = "${google_cloud_scheduler_job.daily_scan.schedule} (${google_cloud_scheduler_job.daily_scan.time_zone})"
}
