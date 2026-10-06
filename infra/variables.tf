variable "project_id" {
  description = "Existing personal GCP project with billing enabled."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Use a GCP project ID, not its display name or number."
  }
}

variable "region" {
  description = "Must match the bootstrap region."
  type        = string
  default     = "europe-west1"
}

variable "image" {
  description = "Scanner image digest in this project's bootstrapped registry."
  type        = string
  validation {
    condition     = can(regex("^${var.region}-docker\\.pkg\\.dev/${var.project_id}/market-scanner/market-scanner-adk@sha256:[0-9a-f]{64}$", var.image))
    error_message = "Use an immutable market-scanner-adk digest from this project's market-scanner repository."
  }
}

variable "vertex_location" {
  description = "Vertex inference location, independent of the Cloud Run region."
  type        = string
  default     = "eu"
}

variable "model" {
  type    = string
  default = "gemini-3.8-flash"
}

variable "database_secret_version" {
  description = "Numeric version of market-scanner-database-url containing the writer URL."
  type        = string
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.database_secret_version))
    error_message = "Pin an existing numeric secret version; do not use latest."
  }
}

variable "database_schema" {
  type    = string
  default = "market_scanner"
  validation {
    condition     = can(regex("^[a-z_][a-z0-9_]{0,62}$", var.database_schema))
    error_message = "Use a PostgreSQL schema accepted by the application."
  }
}

variable "invoker_members" {
  description = "Explicit users or service accounts allowed to call this private service."
  type        = set(string)
  default     = []
  validation {
    condition     = alltrue([for member in var.invoker_members : can(regex("^(user|serviceAccount):[^ ]+@[^ ]+$", member))])
    error_message = "Use user:email or serviceAccount:email; public invocation is not supported."
  }
}
