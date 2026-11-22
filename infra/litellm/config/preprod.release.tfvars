# Deployed preprod release. Update it in the same change as each deployment.
# Pass after the backend-independent defaults and before config/preprod-models.tfvars.
# Personal identities and external endpoints stay in ignored local files
# (identities, SSO, agent governance, key alert); this repository is public.
project_id      = "preprod-deep-copy"
region          = "europe-west1"
vertex_location = "eu"
stage           = "service"

# Named admins sign in with Google SSO; the shared admin login is disabled.
disable_env_credential_login = true

secret_versions = {
  database-url = "2"
  database-ca  = "1"
  master-key   = "1"
  salt-key     = "1"
  ui-password  = "1"
}

# Provider API keys uploaded with scripts/upload_provider_key.py (values stay in Secret Manager).
provider_secret_versions = { typesafe = "1" }

client_service_accounts = {
  momentum           = "momentum-worker@preprod-deep-copy.iam.gserviceaccount.com"
  market-scanner-adk = "market-scanner-adk@preprod-deep-copy.iam.gserviceaccount.com"
}
client_tools_image  = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/market-scanner-adk@sha256:c18b4fb4b341bf530476842b79f856e920480f6077eadc6574280ab6ff79c48d"
client_key_versions = { market-scanner-adk = "2" }

# EUR 30 converted with ECB reference rate 2026-10-06: EUR/USD 1.1269.
global_budget_usd = 33.80

# Patched 1.108.0 pair published 2026-11-18 (see SECURITY.md).
release_images = {
  proxy      = "europe-west1-docker.pkg.dev/preprod-deep-copy/litellm-release/litellm@sha256:a55d747fdeaa67eaacc6b187504e2c786815acf841905baed92ac234c08c5316"
  migrations = "europe-west1-docker.pkg.dev/preprod-deep-copy/litellm-release/litellm-migrations@sha256:cdd2f2b42af68c3bb624724129bfb0983448ed6e8fe3db3b991a782395704086"
}
