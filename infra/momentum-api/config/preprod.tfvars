project_id = "preprod-deep-copy"
region     = "europe-west1"
# Deployed release. Update it in the same change as each deployment.
# Cloud Build 9b531a53-81fa-47c8-b9e3-2462bcb2d25f, 2026-11-17.
image                   = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/momentum-api@sha256:8585b320eb5e34d51118612afe1d7aa9a72e34d5e0a5ea8874962b444bd5a831"
database_secret_version = "1"
ca_secret_version       = "1"
suggestion_key_version  = "1"
# Personal invoker identities stay in ignored config/identities.local.tfvars.
