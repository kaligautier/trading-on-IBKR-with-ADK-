variable "project_id" {
  type = string
}
variable "region" {
  type    = string
  default = "europe-west1"
}
variable "image" {
  type = string
  validation {
    condition     = can(regex("^${var.region}-docker\\.pkg\\.dev/${var.project_id}/market-scanner/momentum-public-mcp@sha256:[0-9a-f]{64}$", var.image))
    error_message = "Use an immutable momentum-public-mcp image in the destination registry."
  }
}
variable "caller_key_resource" {
  description = "Secret Manager resource name containing the caller signing key."
  type        = string
  default     = "momentum-mcp-caller-key"
}
variable "caller_key_version" {
  type = string
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.caller_key_version))
    error_message = "Pin a numeric secret version."
  }
}
variable "trusted_proxies" {
  type        = string
  default     = ""
  description = "Verified immediate proxy CIDRs only; empty uses the direct peer for local per-instance throttling."
}
variable "log_success_sample_rate" {
  type        = number
  default     = 1
  description = "Retained fraction of successful fast requests; errors and slow requests always remain."
  validation {
    condition     = var.log_success_sample_rate >= 0 && var.log_success_sample_rate <= 1
    error_message = "Log success sampling must be between zero and one."
  }
}
variable "log_slow_request_ms" {
  type        = number
  default     = 2000
  description = "Always retain canonical events at or above this duration in milliseconds."
  validation {
    condition     = var.log_slow_request_ms >= 1 && floor(var.log_slow_request_ms) == var.log_slow_request_ms
    error_message = "The slow-request threshold must be a positive integer."
  }
}
