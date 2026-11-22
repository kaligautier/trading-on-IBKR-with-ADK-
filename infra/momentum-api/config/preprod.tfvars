project_id = "preprod-deep-copy"
region     = "europe-west1"
# Deployed release. Update it in the same change as each deployment.
# Cloud Build 9b531a53-81fa-47c8-b9e3-2462bcb2d25f, 2026-11-17.
image                   = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/momentum-api@sha256:cef4aada3e2845b37095296dd687217447da296bf7399058167655f79f9a7f38"
database_secret_version = "1"
ca_secret_version       = "1"
suggestion_key_version  = "1"
# Personal invoker identities stay in ignored config/identities.local.tfvars.
