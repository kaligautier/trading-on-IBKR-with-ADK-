variable "project_id" {
  type        = string
  description = "Project whose spend is capped and whose services are disabled."
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Use a GCP project ID, not its display name or number."
  }
}
variable "region" {
  type    = string
  default = "europe-west1"
}
variable "billing_account_id" {
  type        = string
  description = "Billing account that pays for the project, as XXXXXX-XXXXXX-XXXXXX."
  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account_id))
    error_message = "Use the billing account ID, not its display name."
  }
}
variable "budget_amount" {
  type        = number
  default     = 50
  description = "Monthly budget. Services are disabled once spend reaches it."
  validation {
    condition     = var.budget_amount > 0
    error_message = "Use a positive amount."
  }
}
variable "currency_code" {
  type        = string
  default     = "EUR"
  description = "Must match the billing account currency."
}
variable "services_to_disable" {
  type        = set(string)
  default     = ["aiplatform.googleapis.com"]
  description = "APIs disabled when the budget is spent. Keep to the APIs a leaked credential could abuse; do not list serviceusage, run or storage."
  validation {
    condition     = length(var.services_to_disable) > 0 && alltrue([for s in var.services_to_disable : can(regex("^[a-z0-9.-]+\\.googleapis\\.com$", s))])
    error_message = "List at least one *.googleapis.com service."
  }
}
variable "alert_thresholds" {
  type        = list(number)
  default     = [0.5, 0.8, 1.0]
  description = "Fractions of the budget that publish a notification. The function only cuts at or above 100%."
  validation {
    condition     = length(var.alert_thresholds) > 0 && alltrue([for t in var.alert_thresholds : t > 0 && t <= 1])
    error_message = "Use fractions in (0, 1]."
  }
}
