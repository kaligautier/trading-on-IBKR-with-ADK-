project_id         = "example-project"
gateway_url        = "https://gateway.example.com"
master_key_version = "1"
models             = ["gemini-3.8-flash"]
# Set the actual team ID and import_team = true when adopting an existing team.
agents = {
  scanner = {
    # Existing key: fill BOTH fields from the deployed inventory before apply.
    # secret_version    = "1"
    # existing_token_id = "<64-character SHA-256 management ID>"
  }
  weekly = {
    max_budget      = 4
    budget_duration = "7d"
  }
}
