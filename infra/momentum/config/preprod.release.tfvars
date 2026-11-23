# Deployed preprod release, read from Cloud Run on 2026-11-18.
# Worker image: Cloud Build a42bc0f1-5fe5-42d1-8118-2e3eda39c116, 2026-11-17.
image = "europe-west1-docker.pkg.dev/preprod-deep-copy/momentum/worker@sha256:e85eea487cd889b3667979870e59affd5b07fbaea7dc7bdc6414c263b5f981e5"
# Rotated LiteLLM key (2026-11-17) and database URLs in use.
llm_key_version          = "2"
session_database_version = "2"
result_database_version  = "2"
