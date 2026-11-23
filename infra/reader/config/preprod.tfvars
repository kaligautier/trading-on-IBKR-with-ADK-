# Deployed preprod release. Update it in the same change as each deployment.
# Image: Cloud Build 35d93b06-8a50-41f7-bcae-d6d064934813 (main 52f9528), 2026-11-18.
project_id              = "preprod-deep-copy"
region                  = "europe-west1"
image                   = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/market-scanner-api@sha256:3dc6aa5a56e413d2a4c1e69cd8b202729bce327219def7437f1845cecf1ede98"
database_secret_version = "2"
ca_secret_id            = "litellm-database-ca"
ca_secret_version       = "1"
# Personal invoker identities stay in ignored config/identities.local.tfvars.
