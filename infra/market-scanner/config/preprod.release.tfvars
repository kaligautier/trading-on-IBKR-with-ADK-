# Deployed preprod release. Update it in the same change as each deployment.
# Image: deployed by run 45047127548 (main 27c95f7, AIP-193 errors), 2026-11-23.
image                   = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/market-scanner-adk@sha256:8d654a98e801224208a3b217c6cf3d27765f46e7bb2e0ca14801b93e171e202c"
database_secret_version = "3"
litellm_gateway = {
  url         = "https://litellm-gateway-gdezc6bzrq-ew.a.run.app"
  key_secret  = "litellm-client-market-scanner-adk"
  key_version = "2"
  network     = "private-services"
  subnetwork  = "cloud-run-egress"
}
