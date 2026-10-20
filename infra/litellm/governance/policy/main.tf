terraform {
  required_version = ">= 1.11, < 2.0"
  required_providers {
    litellm = { source = "BerriAI/litellm", version = "= 1.106.0" }
  }
}

variable "models" {
  type = list(string)
  validation {
    condition     = length(var.models) > 0 && !contains(var.models, "*")
    error_message = "Declare an explicit, nonempty model catalog."
  }
}
variable "team_id" {
  type    = string
  default = "agents"
}
variable "agents" {
  type = map(object({
    max_budget            = optional(number, 3)
    budget_duration       = optional(string, "1d")
    rpm_limit             = optional(number, 10)
    tpm_limit             = optional(number, 100000)
    max_parallel_requests = optional(number, 2)
    existing_token_id     = optional(string)
  }))
  validation {
    condition = alltrue([for name, agent in var.agents :
      can(regex("^[a-z][a-z0-9-]{2,40}$", name)) && agent.max_budget > 0 &&
      can(regex("^[1-9][0-9]*[dh]$", agent.budget_duration)) &&
      agent.rpm_limit > 0 && agent.tpm_limit > 0 && agent.max_parallel_requests > 0 &&
      (agent.existing_token_id == null ? true : can(regex("^[0-9a-f]{64}$", agent.existing_token_id)))
    ])
    error_message = "Use safe agent names, positive limits, a duration such as 1d/7d, and SHA-256 import IDs."
  }
}
variable "client_keys" {
  type      = map(string)
  sensitive = true
  ephemeral = true
  validation {
    condition = toset(keys(var.client_keys)) == toset(keys(var.agents)) && alltrue([
      for name, agent in var.agents : agent.existing_token_id == null ? true :
      try(sha256(var.client_keys[name]) == agent.existing_token_id, false)
    ])
    error_message = "Every agent needs a credential; imported IDs must match the selected secret version."
  }
}

resource "litellm_team" "agents" {
  team_id    = var.team_id
  team_alias = "Agents"
  models     = var.models
  lifecycle {
    prevent_destroy = true
    postcondition {
      condition     = self.max_budget == null || self.max_budget == 0
      error_message = "The agents team must have no shared budget. Adopt a budget-free team to keep per-agent budgets independent."
    }
  }
}
resource "litellm_key" "agent" {
  for_each              = var.agents
  key                   = var.client_keys[each.key]
  key_alias             = each.key
  team_id               = litellm_team.agents.id
  models                = var.models
  allowed_routes        = ["/v1beta/models/*"]
  max_budget            = each.value.max_budget
  budget_duration       = each.value.budget_duration
  rpm_limit             = each.value.rpm_limit
  tpm_limit             = each.value.tpm_limit
  max_parallel_requests = each.value.max_parallel_requests
  duration              = "30d"
  # Keep the alias and expiry when adopting an existing key.
  lifecycle {
    ignore_changes = [key_alias, duration]
    postcondition {
      condition     = each.value.existing_token_id == null ? true : self.id == each.value.existing_token_id
      error_message = "The Terraform key ID differs from the selected credential. Import the replacement explicitly before changing policy."
    }
  }
}
output "token_ids" {
  value = { for name, key in litellm_key.agent : name => key.id }
}
