# Deployed preprod release, read from Cloud Run on 2026-11-18.
# Worker image: Cloud Build a42bc0f1-5fe5-42d1-8118-2e3eda39c116, 2026-11-17.
image = "europe-west1-docker.pkg.dev/preprod-deep-copy/momentum/worker@sha256:00c06b212117271f5a6cc6f877c5d16c19bd0a66b929c1ac24134e16d0f73e50"
# Rotated LiteLLM key (2026-11-17) and database URLs in use.
llm_key_version          = "2"
session_database_version = "2"
result_database_version  = "2"
