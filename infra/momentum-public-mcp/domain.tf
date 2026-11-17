# Explicitly transfer the existing hostname; the Google CNAME stays unchanged.
resource "google_cloud_run_domain_mapping" "mcp" {
  count    = var.enable_domain_mapping ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = "mcp.deepcopy.fr"

  metadata {
    namespace = var.project_id
  }
  spec {
    route_name     = google_cloud_run_v2_service.mcp.name
    force_override = true
  }
  lifecycle {
    prevent_destroy = true
  }
}

output "domain_resource_records" {
  description = "Required DNS records for the public MCP hostname."
  value       = { for mapping in google_cloud_run_domain_mapping.mcp : mapping.name => mapping.status[0].resource_records }
}
