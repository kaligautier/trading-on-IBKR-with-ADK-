mock_provider "google" {}
mock_provider "google-beta" {}
override_resource {
  target          = google_pubsub_topic.key_rotation
  override_during = plan
  values          = { id = "projects/example-project/topics/litellm-agent-key-rotation" }
}
variables {
  project_id = "example-project"
  client_service_accounts = {
    scanner = "scanner@example-project.iam.gserviceaccount.com"
  }
}

run "alert_disabled_by_default" {
  command = plan
  assert {
    condition     = length(google_pubsub_topic.key_rotation) == 0 && length(google_monitoring_alert_policy.key_rotation_due) == 0 && length(google_secret_manager_secret.client_key["scanner"].rotation) == 0 && length(google_secret_manager_secret.client_key["scanner"].topics) == 0
    error_message = "Without key_expiry_alert, no reminder or alert may be created."
  }
}

run "reminder_fires_before_expiry" {
  command = plan
  variables {
    key_expiry_alert = {
      email      = "ops@example.com"
      rotated_at = "2026-11-17T22:14:19Z"
    }
  }
  assert {
    condition     = one(google_secret_manager_secret.client_key["scanner"].rotation).next_rotation_time == "2026-12-12T22:14:19Z" && one(google_secret_manager_secret.client_key["scanner"].rotation).rotation_period == "2592000s"
    error_message = "The reminder must fire lead_days before the 30-day expiry, then every key lifetime."
  }
  assert {
    condition     = one(google_secret_manager_secret.client_key["scanner"].topics).name == "projects/example-project/topics/litellm-agent-key-rotation"
    error_message = "The rotation reminder must publish to the dedicated topic."
  }
  assert {
    condition     = google_pubsub_topic_iam_member.key_rotation_publisher[0].role == "roles/pubsub.publisher" && google_monitoring_notification_channel.key_expiry[0].labels.email_address == "ops@example.com"
    error_message = "Secret Manager must be able to publish and the alert must notify the configured e-mail."
  }
  assert {
    condition     = length(google_monitoring_alert_policy.key_rotation_due) == 1 && length(google_monitoring_alert_policy.key_expired) == 1
    error_message = "Both the reminder alert and the expired-key safety net are required."
  }
  assert {
    condition     = strcontains(google_monitoring_alert_policy.key_expired[0].conditions[0].condition_matched_log[0].filter, "NOT resource.labels.service_name = \"litellm\"")
    error_message = "The expired-key alert must ignore admin UI session expiry and keep watching the gateway and jobs."
  }
}

run "reject_lead_longer_than_key" {
  command = plan
  variables {
    key_expiry_alert = {
      email      = "ops@example.com"
      rotated_at = "2026-11-17T22:14:19Z"
      lead_days  = 30
    }
  }
  expect_failures = [var.key_expiry_alert]
}
