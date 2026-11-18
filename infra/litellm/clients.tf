variable "client_service_accounts" {
  description = "Existing application identities allowed to read their private-gateway virtual keys."
  type        = map(string)
  default     = {}
  validation {
    condition = alltrue([for name, email in var.client_service_accounts :
      can(regex("^[a-z][a-z0-9-]{2,40}$", name)) &&
      can(regex("^[a-z][a-z0-9-]+@${var.project_id}\\.iam\\.gserviceaccount\\.com$", email))
    ])
    error_message = "Use explicit service accounts in this project and safe client names."
  }
}

resource "google_secret_manager_secret" "client_key" {
  for_each = setunion(
    toset(keys(var.client_service_accounts)),
    local.governance_enabled ? toset(keys(var.agent_governance.agents)) : toset([]),
  )
  project             = var.project_id
  secret_id           = "litellm-client-${each.key}"
  version_destroy_ttl = "2592000s"
  replication {
    auto {}
  }
  # Rotation is only a reminder: Secret Manager publishes to the topic, nothing rotates.
  dynamic "topics" {
    for_each = local.key_alert_enabled ? [google_pubsub_topic.key_rotation[0].id] : []
    content {
      name = topics.value
    }
  }
  dynamic "rotation" {
    for_each = local.key_alert_enabled ? [local.key_reminder_time] : []
    content {
      next_rotation_time = rotation.value
      rotation_period    = "${var.key_expiry_alert.key_days * 86400}s"
    }
  }
  depends_on = [google_pubsub_topic_iam_member.key_rotation_publisher]
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret_iam_member" "client_key" {
  for_each  = var.client_service_accounts
  project   = var.project_id
  secret_id = google_secret_manager_secret.client_key[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}
