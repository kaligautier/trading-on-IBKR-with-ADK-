terraform {
  required_version = ">= 1.9, < 2.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
  # Budgets are billed to the quota project, not the caller's default one.
  user_project_override = true
  billing_project       = var.project_id
}

data "google_project" "target" {
  project_id = var.project_id
}

resource "google_project_service" "apis" {
  for_each = toset([
    "billingbudgets.googleapis.com",
    "cloudbilling.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudfunctions.googleapis.com",
    "run.googleapis.com",
    "eventarc.googleapis.com",
    "pubsub.googleapis.com",
    "artifactregistry.googleapis.com",
    "serviceusage.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_pubsub_topic" "budget" {
  project    = var.project_id
  name       = "budget-guard-notifications"
  depends_on = [google_project_service.apis]
}

resource "google_billing_budget" "guard" {
  billing_account = var.billing_account_id
  display_name    = "${var.project_id} - ${var.budget_amount} ${var.currency_code} hard stop"

  budget_filter {
    projects               = ["projects/${data.google_project.target.number}"]
    calendar_period        = "MONTH"
    credit_types_treatment = "EXCLUDE_ALL_CREDITS"
  }
  amount {
    specified_amount {
      currency_code = var.currency_code
      units         = tostring(floor(var.budget_amount))
      nanos         = floor((var.budget_amount - floor(var.budget_amount)) * 1000000000)
    }
  }
  dynamic "threshold_rules" {
    for_each = toset(var.alert_thresholds)
    content {
      threshold_percent = threshold_rules.value
      spend_basis       = "CURRENT_SPEND"
    }
  }
  all_updates_rule {
    pubsub_topic   = google_pubsub_topic.budget.id
    schema_version = "1.0"
  }
  depends_on = [google_project_service.apis]
}

# Least privilege: the function may only disable services, nothing else.
resource "google_project_iam_custom_role" "service_disabler" {
  project     = var.project_id
  role_id     = "budgetGuardServiceDisabler"
  title       = "Budget guard service disabler"
  permissions = ["serviceusage.services.disable", "serviceusage.services.get", "serviceusage.services.use", "serviceusage.operations.get"]
}

resource "google_service_account" "guard" {
  project      = var.project_id
  account_id   = "budget-guard"
  display_name = "Budget guard kill switch"
}

resource "google_project_iam_member" "disable" {
  project = var.project_id
  role    = google_project_iam_custom_role.service_disabler.id
  member  = "serviceAccount:${google_service_account.guard.email}"
}

resource "google_project_iam_member" "event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.guard.email}"
}

data "archive_file" "source" {
  type        = "zip"
  source_dir  = "${path.module}/../../apps/platform/budget-guard"
  output_path = "${path.module}/.build/function.zip"
  excludes    = ["__pycache__", "*.pyc"]
}

resource "google_storage_bucket" "source" {
  project                     = var.project_id
  name                        = "${var.project_id}-budget-guard-src"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = true
  depends_on                  = [google_project_service.apis]
}

resource "google_storage_bucket_object" "source" {
  bucket = google_storage_bucket.source.name
  name   = "function-${data.archive_file.source.output_md5}.zip"
  source = data.archive_file.source.output_path
}

resource "google_cloudfunctions2_function" "guard" {
  project  = var.project_id
  location = var.region
  name     = "budget-guard"
  labels   = { application = "budget-guard" }

  build_config {
    runtime     = "python312"
    entry_point = "stop_spending"
    source {
      storage_source {
        bucket = google_storage_bucket.source.name
        object = google_storage_bucket_object.source.name
      }
    }
  }
  service_config {
    service_account_email          = google_service_account.guard.email
    available_memory               = "256M"
    timeout_seconds                = 60
    max_instance_count             = 1
    ingress_settings               = "ALLOW_INTERNAL_ONLY"
    all_traffic_on_latest_revision = true
    environment_variables = {
      TARGET_PROJECT_ID   = var.project_id
      SERVICES_TO_DISABLE = join(",", sort(tolist(var.services_to_disable)))
    }
  }
  event_trigger {
    trigger_region        = var.region
    event_type            = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic          = google_pubsub_topic.budget.id
    retry_policy          = "RETRY_POLICY_RETRY"
    service_account_email = google_service_account.guard.email
  }
  depends_on = [google_project_iam_member.event_receiver, google_project_iam_member.disable]
}

resource "google_cloud_run_service_iam_member" "trigger" {
  project  = var.project_id
  location = var.region
  service  = google_cloudfunctions2_function.guard.service_config[0].service
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.guard.email}"
}

output "budget_name" {
  value = google_billing_budget.guard.name
}
output "topic" {
  value = google_pubsub_topic.budget.id
}
