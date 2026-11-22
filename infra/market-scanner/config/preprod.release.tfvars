# Deployed preprod release. Update it in the same change as each deployment.
# Image: Cloud Build 3b6f0731-59d7-413a-8c99-1a3a44908cab (main 52f9528), 2026-11-18.
image                   = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/market-scanner-adk@sha256:d363e8403d816d4af387f023fbbdcac276477218239488f1704b84544598efbd"
database_secret_version = "3"
litellm_gateway = {
  url         = "https://litellm-gateway-gdezc6bzrq-ew.a.run.app"
  key_secret  = "litellm-client-market-scanner-adk"
  key_version = "2"
  network     = "private-services"
  subnetwork  = "cloud-run-egress"
}
