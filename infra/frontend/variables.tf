variable "project_id" {
  type        = string
  description = "Existing project containing the private scanner reader and registry."
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "image" {
  type        = string
  description = "Tested immutable frontend image digest."
  validation {
    condition     = can(regex("^${var.region}-docker\\.pkg\\.dev/${var.project_id}/market-scanner/market-scanner-front@sha256:[0-9a-f]{64}$", var.image))
    error_message = "Use an immutable market-scanner-front image in this project's registry."
  }
}
