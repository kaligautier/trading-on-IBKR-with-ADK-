# Deployed preprod release. Update it in the same change as each deployment.
# Image: Cloud Build d4400957-cb00-4178-98f3-6f85109c006b (main e3d2c76), deployed by run 45043890830, 2026-11-22.
image                   = "europe-west1-docker.pkg.dev/preprod-deep-copy/market-scanner/market-scanner-adk@sha256:d363e8403d816d4af387f023fbbdcac276477218239488f1704b84544598efbd"
database_secret_version = "3"
litellm_gateway = {
  url         = "https://litellm-gateway-gdezc6bzrq-ew.a.run.app"
  key_secret  = "litellm-client-market-scanner-adk"
  key_version = "2"
  network     = "private-services"
  subnetwork  = "cloud-run-egress"
}
