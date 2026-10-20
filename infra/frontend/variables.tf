variable "project_id" {
  type        = string
  description = "Destination project already provisioned by infra/bootstrap and infra/reader."
  validation {
    condition     = var.project_id == "preprod-deep-copy"
    error_message = "This migration targets preprod-deep-copy; never deploy it back into Demo ADK."
  }
}

variable "region" {
  type    = string
  default = "europe-west1"
  validation {
    condition     = var.region == "europe-west1"
    error_message = "Use europe-west1, matching the reader and supporting domain mappings."
  }
}

variable "image" {
  type        = string
  description = "Frontend image built in the destination project, pinned by digest."
  validation {
    condition     = can(regex("^${var.region}-docker\\.pkg\\.dev/${var.project_id}/market-scanner/deepcopy-front@sha256:[0-9a-f]{64}$", var.image))
    error_message = "Use a destination-project deepcopy-front digest; tags and Demo ADK images are forbidden."
  }
}

variable "enable_domain_mappings" {
  type        = bool
  default     = false
  description = "Transfer deepcopy.fr and www.deepcopy.fr only after validating the new run.app URL. Never toggle back to false after cutover."
}
