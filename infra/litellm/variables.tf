variable "project_id" {
  description = "GCP project whose shared bootstrap has already been applied."
  type        = string
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
  description = "Official LiteLLM v1.103.1 image index, verified against GHCR on 2026-09-30."
  type        = string
  default     = "sha256:df15400b5b80925c45d3fd53f8f7a6c0eaa8a25a86833e1b358002e129018943"
  validation {
    condition     = can(regex("^sha256:[0-9a-f]{64}$", var.proxy_digest))
    error_message = "Use an immutable image digest."
  }
}

variable "migrations_digest" {
  description = "Official LiteLLM migrations v1.103.1 image index; upgrade together with proxy_digest."
  type        = string
  default     = "sha256:906b157d60b3aa4f42b0a714e28fff4d1acf2f4a0a414c637d9a603a0b13793e"
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
