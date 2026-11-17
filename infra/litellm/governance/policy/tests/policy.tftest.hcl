mock_provider "litellm" {}
override_data {
  target = data.litellm_team.agents
  values = { max_budget = null }
}
variables {
  models      = ["gemini-test"]
  agents      = { scanner = {}, weekly = { max_budget = 4, budget_duration = "7d" } }
  client_keys = { scanner = "offline-scanner", weekly = "offline-weekly" }
}
run "independent_daily_and_weekly_budgets" {
  command = plan
  assert {
    condition = (
      litellm_key.agent["scanner"].max_budget == 3 && litellm_key.agent["scanner"].budget_duration == "1d" &&
      litellm_key.agent["weekly"].max_budget == 4 && litellm_key.agent["weekly"].budget_duration == "7d" &&
      litellm_key.agent["scanner"].allowed_routes == tolist(["/v1beta/models/*"]) &&
      litellm_key.agent["weekly"].rpm_limit == 10 && litellm_key.agent["weekly"].max_parallel_requests == 2
    )
    error_message = "Each key must receive its own budget/window and inference-only access."
  }
}
run "reject_zero_budget" {
  command = plan
  variables { agents = { scanner = { max_budget = 0 }, weekly = {} } }
  expect_failures = [var.agents]
}
run "reject_unbounded_models" {
  command = plan
  variables { models = ["*"] }
  expect_failures = [var.models]
}
run "reject_wrong_import_secret" {
  command = plan
  variables { agents = { scanner = { existing_token_id = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }, weekly = {} } }
  expect_failures = [var.client_keys]
}
