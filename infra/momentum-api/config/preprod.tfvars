project_id = "preprod-deep-copy"
region     = "europe-west1"
# Cloud Build f56460a8-4e9f-47ce-9f88-3140728fbb26, 2026-10-24.
image                   = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/momentum-api@sha256:78eaddc64c8959a8ddab865e04a1616c9164d0313d81670c587f904441dccdde"
database_secret_version = "1"
ca_secret_version       = "1"
suggestion_key_version  = "1"
# Preserve explicit invokers in the existing private release variables.
