variable "project_id" {
  type        = string
  description = "Existing GCP project with Cloud Run, Secret Manager and registry enabled."
}
variable "region" {
  type    = string
  default = "europe-west1"
}
variable "image" {
  type        = string
  description = "Immutable API image in the existing market-scanner registry."
  validation {
    condition     = can(regex("^${var.region}-docker\\.pkg\\.dev/${var.project_id}/market-scanner/market-scanner-api@sha256:[0-9a-f]{64}$", var.image))
    error_message = "Use an immutable market-scanner-api image digest in this project."
  }
}
variable "database_secret_id" {
  type    = string
  default = "market-scanner-reader-database-url"
}
variable "database_secret_version" {
  type        = string
  description = "Existing reader URL with sslmode=verify-full&sslrootcert=/etc/database/ca.pem."
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.database_secret_version))
    error_message = "Pin a numeric secret version."
  }
}
variable "ca_secret_id" {
  type    = string
  default = "market-scanner-database-ca"
}
variable "ca_secret_version" {
  type = string
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.ca_secret_version))
    error_message = "Pin a numeric CA secret version."
  }
}
variable "invoker_members" {
  type        = set(string)
  default     = []
  description = "Explicit users or service accounts permitted to consult reports."
  validation {
    condition     = alltrue([for member in var.invoker_members : can(regex("^(user|serviceAccount):[^ ]+@[^ ]+$", member))])
    error_message = "Only explicit user or serviceAccount members are allowed."
  }
}
