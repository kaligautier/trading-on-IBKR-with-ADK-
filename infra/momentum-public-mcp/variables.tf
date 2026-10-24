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
