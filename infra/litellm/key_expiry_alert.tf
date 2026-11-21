variable "key_expiry_alert" {
  description = "Optional e-mail alert before agent keys expire. rotated_at is the RFC 3339 time of the last agent-key rotation; update it after every rotation."
  type = object({
    email      = string
    rotated_at = string
    key_days   = optional(number, 30)
    lead_days  = optional(number, 5)
  })
  default = null
  validation {
    condition = var.key_expiry_alert == null ? true : (
      can(regex("^[^@ ]+@[^@ ]+$", var.key_expiry_alert.email)) &&
      can(timeadd(var.key_expiry_alert.rotated_at, "0s")) &&
      var.key_expiry_alert.lead_days >= 1 &&
      var.key_expiry_alert.lead_days < var.key_expiry_alert.key_days
    )
    error_message = "Use a valid e-mail, an RFC 3339 rotated_at, and 1 <= lead_days < key_days."
  }
}

locals {
  key_alert_enabled = var.key_expiry_alert != null
  # Secret Manager publishes SECRET_ROTATE to the topic at this time, then every key lifetime.
  key_reminder_time = local.key_alert_enabled ? timeadd(
    var.key_expiry_alert.rotated_at,
    "${(var.key_expiry_alert.key_days - var.key_expiry_alert.lead_days) * 24}h",
  ) : null
}

resource "google_pubsub_topic" "key_rotation" {
  count   = local.key_alert_enabled ? 1 : 0
  project = var.project_id
  name    = "litellm-agent-key-rotation"
}

resource "google_project_service_identity" "secretmanager" {
  count    = local.key_alert_enabled ? 1 : 0
  provider = google-beta
  project  = var.project_id
  service  = "secretmanager.googleapis.com"
}

resource "google_pubsub_topic_iam_member" "key_rotation_publisher" {
  count   = local.key_alert_enabled ? 1 : 0
  project = var.project_id
  topic   = google_pubsub_topic.key_rotation[0].name
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_project_service_identity.secretmanager[0].email}"
}

resource "google_monitoring_notification_channel" "key_expiry" {
  count        = local.key_alert_enabled ? 1 : 0
  project      = var.project_id
  display_name = "LiteLLM agent key expiry"
  type         = "email"
  labels       = { email_address = var.key_expiry_alert.email }
}

resource "google_monitoring_alert_policy" "key_rotation_due" {
  count        = local.key_alert_enabled ? 1 : 0
  project      = var.project_id
  display_name = "LiteLLM agent keys expire soon"
  combiner     = "OR"
  conditions {
    display_name = "Secret Manager rotation reminder published"
    condition_threshold {
      filter          = "resource.type = \"pubsub_topic\" AND resource.labels.topic_id = \"${google_pubsub_topic.key_rotation[0].name}\" AND metric.type = \"pubsub.googleapis.com/topic/send_message_operation_count\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
  alert_strategy { auto_close = "604800s" }
  documentation {
    mime_type = "text/markdown"
    content   = "Agent keys expire in about ${var.key_expiry_alert.lead_days} days. Rotate them with the runbook in `infra/litellm/governance/README.md`, then update `key_expiry_alert.rotated_at`."
  }
  notification_channels = [google_monitoring_notification_channel.key_expiry[0].id]
  depends_on            = [google_pubsub_topic_iam_member.key_rotation_publisher]
}

# Safety net: an expired key reached an agent anyway.
resource "google_monitoring_alert_policy" "key_expired" {
  count        = local.key_alert_enabled ? 1 : 0
  project      = var.project_id
  display_name = "LiteLLM agent key expired"
  combiner     = "OR"
  conditions {
    display_name = "Expired Key error in Cloud Run logs"
    condition_matched_log {
      # Agents reach LiteLLM through the gateway. The admin UI logs the same error
      # when an operator's browser session expires, which is not an agent key.
      filter = "resource.type = (\"cloud_run_revision\" OR \"cloud_run_job\") AND \"Expired Key\" AND NOT resource.labels.service_name = \"litellm\""
    }
  }
  alert_strategy {
    notification_rate_limit { period = "3600s" }
    auto_close = "86400s"
  }
  documentation {
    mime_type = "text/markdown"
    content   = "An agent called LiteLLM with an expired key. Rotate the keys now with the runbook in `infra/litellm/governance/README.md`."
  }
  notification_channels = [google_monitoring_notification_channel.key_expiry[0].id]
}
