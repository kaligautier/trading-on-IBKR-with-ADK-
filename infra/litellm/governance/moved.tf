# Adopt the previous flat governance state without creating duplicate objects.
moved {
  from = litellm_team.agents
  to   = module.policy.litellm_team.agents
}
moved {
  from = litellm_key.agent
  to   = module.policy.litellm_key.agent
}
