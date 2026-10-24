variable "project_id" {
  description = "GCP project whose shared bootstrap has already been applied."
  type        = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "Use a GCP project ID, not its display name or number."
  }
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "stage" {
  description = "Apply foundation, populate secrets, apply migrations, execute the job, then apply service."
  type        = string
  default     = "foundation"
  validation {
    condition     = contains(["foundation", "migrations", "service"], var.stage)
    error_message = "Choose foundation, migrations, or service. Do not go backwards after deployment."
  }
}

variable "iap_members" {
  description = "Explicit users or groups permitted to reach LiteLLM through IAP."
  type        = set(string)
  default     = []
  validation {
    condition = (
      alltrue([for member in var.iap_members : can(regex("^(user|group):[^ @]+@[^ @]+$", member))]) &&
      (var.stage != "service" || length(var.iap_members) > 0)
    )
    error_message = "Use explicit user:email or group:email principals; service stage requires at least one."
  }
}

variable "secret_versions" {
  description = "Numeric Secret Manager versions only; values are uploaded outside Terraform."
  type        = map(string)
  default     = {}
  validation {
    condition = (
      alltrue([for value in values(var.secret_versions) : can(regex("^[1-9][0-9]*$", value))]) &&
      alltrue([for key in keys(var.secret_versions) : contains(["database-url", "master-key", "salt-key", "ui-password", "database-ca"], key)]) &&
      (var.stage == "foundation" || alltrue([
        for key in ["database-url", "master-key", "salt-key", "ui-password"] : contains(keys(var.secret_versions), key)
      ]))
    )
    error_message = "Pin numeric versions for database-url, master-key, salt-key and ui-password; database-ca is optional."
  }
}

variable "proxy_digest" {
  description = "Official LiteLLM v1.106.2 image index, verified against GHCR on 2026-10-21."
  type        = string
  default     = "sha256:7294b90f868c5c38c99b83021c7ba46f9b439e95f8e32964c925c7d2563a03f7"
  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.proxy_digest))
    error_message = "Use an immutable image digest."
  }
}

variable "migrations_digest" {
  description = "Official LiteLLM migrations v1.106.2 image index; upgrade together with proxy_digest."
  type        = string
  default     = "sha256:bdcb8d71f3cc6344beeb7280b8865cfebfbe218426dd12f079ee4ea99dc10563"
  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.migrations_digest))
    error_message = "Use an immutable image digest."
  }
}

variable "vertex_location" {
  type    = string
  default = "eu"
}

variable "model" {
  type    = string
  default = "gemini-3.8-flash"
}

variable "additional_vertex_models" {
  description = "Additional explicit Gemini IDs exposed through the existing Vertex identity and location."
  type        = set(string)
  default     = []
  validation {
    condition = alltrue([for model in var.additional_vertex_models :
      can(regex("^gemini-[a-zA-Z0-9._-]+$", model)) && model != var.model
    ])
    error_message = "Use explicit Gemini model IDs without wildcards, distinct from the primary model."
  }
}

variable "global_budget_usd" {
  description = "Optional global LLM spend budget in USD over 30 days, shared through the proxy database. Excludes infrastructure costs."
  type        = number
  default     = null
  validation {
    condition     = var.global_budget_usd == null ? true : var.global_budget_usd > 0
    error_message = "Use a positive USD budget; null leaves the global limit unconfigured."
  }
}
