# Deployed preprod release. Update it in the same change as each deployment.
# Image: Cloud Build 35d93b06-8a50-41f7-bcae-d6d064934813 (main 52f9528), 2026-11-18.
project_id              = "preprod-deep-copy"
region                  = "europe-west1"
image                   = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/market-scanner-api@sha256:06065d9d71c8fc38ea162f141cac27cc74c88591c6e2013e9ecdb43bcf462193"
database_secret_version = "2"
ca_secret_id            = "litellm-database-ca"
ca_secret_version       = "1"
# Personal invoker identities stay in ignored config/identities.local.tfvars.
