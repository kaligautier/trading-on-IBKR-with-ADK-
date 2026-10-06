output "scanner_url" {
  value = google_cloud_run_v2_service.scanner.uri
}

output "scanner_service_account" {
  value = google_service_account.scanner.email
}

output "scanner_image" {
  value = var.image
}
