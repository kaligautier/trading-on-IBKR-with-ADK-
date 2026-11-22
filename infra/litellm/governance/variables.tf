variable "project_id" { type = string }
variable "gateway_url" {
  type = string
  validation {
    condition     = can(regex("^https://[a-zA-Z0-9.-]+$", var.gateway_url))
    error_message = "Use an HTTPS origin without credentials, path or query."
  }
}
variable "master_key_version" {
  type = string
  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.master_key_version))
    error_message = "Pin a numeric master-key secret version."
  }
}
variable "team_id" {
  type    = string
  default = "agents"
}
variable "import_team" {
  type    = bool
  default = false
}
variable "models" { type = list(string) }
variable "agents" {
  description = "Each agent has its own limits. Adopt existing keys with both a pinned secret version and its SHA-256 token ID."
  type = map(object({
    max_budget            = optional(number, 3)
    budget_duration       = optional(string, "1d")
    rpm_limit             = optional(number, 10)
    tpm_limit             = optional(number, 100000)
    max_parallel_requests = optional(number, 2)
    secret_version        = optional(string)
    existing_token_id     = optional(string)
  }))
  validation {
    condition = alltrue([for agent in var.agents :
      (agent.secret_version == null) == (agent.existing_token_id == null) &&
      (agent.secret_version == null ? true : can(regex("^[1-9][0-9]*$", agent.secret_version)))
    ])
    error_message = "Existing keys require both a numeric secret version and a matching token ID; new keys omit both."
  }
}
