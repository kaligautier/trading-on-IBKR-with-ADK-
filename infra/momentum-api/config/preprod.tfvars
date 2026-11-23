project_id = "preprod-deep-copy"
region     = "europe-west1"
# Deployed release. Update it in the same change as each deployment.
# Cloud Build 9b531a53-81fa-47c8-b9e3-2462bcb2d25f, 2026-11-17.
image                   = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/momentum-api@sha256:7b3e980d4c30fb08ddb2422f1328b095926718c212936f7485390e379febfede"
database_secret_version = "1"
ca_secret_version       = "1"
suggestion_key_version  = "1"
# Personal invoker identities stay in ignored config/identities.local.tfvars.
