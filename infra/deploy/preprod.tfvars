project_id           = "preprod-deep-copy"
github_repository    = "kaligautier/trading-on-IBKR-with-ADK-"
github_repository_id = "1371088733"
github_owner_id      = "145285925"

# Runtime identities of the services and jobs the deployer may update (actAs).
runtime_service_accounts = {
  market-scanner-adk = "market-scanner-adk@preprod-deep-copy.iam.gserviceaccount.com"
  market-scanner-api = "market-scanner-api@preprod-deep-copy.iam.gserviceaccount.com"
  momentum-api       = "momentum-api@preprod-deep-copy.iam.gserviceaccount.com"
  momentum-worker    = "momentum-worker@preprod-deep-copy.iam.gserviceaccount.com"
}
