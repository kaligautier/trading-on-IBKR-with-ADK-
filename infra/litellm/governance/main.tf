terraform {
  required_version = ">= 1.11, < 2.0"
  required_providers {
    google  = { source = "hashicorp/google", version = "~> 7.46" }
    random  = { source = "hashicorp/random", version = "= 3.8.1" }
    litellm = { source = "BerriAI/litellm", version = "= 1.106.0" }
  }
  backend "gcs" {}
}
provider "google" { project = var.project_id }
ephemeral "google_secret_manager_secret_version" "master" {
  secret  = "litellm-master-key"
  version = var.master_key_version
}
provider "litellm" {
  api_base = var.gateway_url
  api_key  = ephemeral.google_secret_manager_secret_version.master.secret_data
}

# Persist new credentials BEFORE registering them with LiteLLM. A failed apply
# can then retry with the same credential, without creating an orphaned key.
ephemeral "random_password" "agent" {
  for_each = { for name, agent in var.agents : name => agent if agent.secret_version == null }
  length   = 64
  special  = false
}
resource "google_secret_manager_secret_version" "agent" {
  for_each               = { for name, agent in var.agents : name => agent if agent.secret_version == null }
  secret                 = "projects/${var.project_id}/secrets/litellm-client-${each.key}"
  secret_data_wo         = "sk-${ephemeral.random_password.agent[each.key].result}"
  secret_data_wo_version = 1
  lifecycle { prevent_destroy = true }
}
ephemeral "google_secret_manager_secret_version" "agent" {
  for_each = var.agents
  secret   = "litellm-client-${each.key}"
  version  = each.value.secret_version != null ? each.value.secret_version : google_secret_manager_secret_version.agent[each.key].version
}
module "policy" {
  source      = "./policy"
  team_id     = var.team_id
  models      = var.models
  agents      = var.agents
  client_keys = { for name, secret in ephemeral.google_secret_manager_secret_version.agent : name => secret.secret_data }
}
output "client_key_versions" {
  value = { for name, agent in var.agents : name => agent.secret_version != null ? agent.secret_version : google_secret_manager_secret_version.agent[name].version }
}
output "token_ids" { value = module.policy.token_ids }

import {
  for_each = var.import_team ? toset([var.team_id]) : toset([])
  to       = module.policy.litellm_team.agents
  id       = each.value
}
import {
  for_each = { for name, agent in var.agents : name => agent.existing_token_id if agent.existing_token_id != null }
  to       = module.policy.litellm_key.agent[each.key]
  id       = each.value
}
