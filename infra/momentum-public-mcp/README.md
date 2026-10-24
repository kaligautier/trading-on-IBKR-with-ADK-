# Public MCP deployment

Independent Terraform roots in `preprod-deep-copy/europe-west1`:

- `build/`: dedicated Cloud Build identity, private source bucket, repository
  publication grants and caller-key secret metadata. Existing Cloud Build API
  and Artifact Registry remain owned by their existing roots.
- This root: public `momentum-public-mcp`, dedicated runtime, additive invocation
  rights on the private `momentum-api` and `market-scanner-api`, and access to a
  single pinned caller-key secret version. No database or ADK permissions.

The Cloud Run `run.app` HTTPS URL is sufficient for web access. This stack does
not take over the existing `mcp.deepcopy.fr` domain mapping. It keeps explicit
scaling limits and disables session affinity. Data APIs remain IAM protected.

```sh
terraform -chdir=infra/momentum-public-mcp/build init -backend-config=preprod.backend.hcl
terraform -chdir=infra/momentum-public-mcp/build plan -out=build.tfplan
terraform -chdir=infra/momentum-public-mcp/build apply build.tfplan
```

Provision a random caller key directly into Secret Manager
`momentum-mcp-caller-key`, outside Terraform. Use a numeric version in the
runtime configuration. Momentum API must use the same key for the original
suggestions caller HMAC validation.

```sh
gcloud builds submit apps/backend/momentum-public-mcp \
  --project=preprod-deep-copy --region=europe-west1 \
  --config=infra/momentum-public-mcp/cloudbuild.yaml \
  --service-account=projects/preprod-deep-copy/serviceAccounts/momentum-mcp-builder@preprod-deep-copy.iam.gserviceaccount.com \
  --gcs-source-staging-dir=gs://preprod-deep-copy-mcp-build-sources/source
```

The app's `.gcloudignore` excludes environments, tests, caches and credentials.
Builds use a non-root Python image and `uv sync --frozen --no-dev`. Record the
resulting image digest and numeric secret version in the release tfvars:

```sh
terraform -chdir=infra/momentum-public-mcp init -backend-config=config/preprod.backend.hcl
terraform -chdir=infra/momentum-public-mcp plan -var-file=config/preprod.tfvars -out=release.tfplan
terraform -chdir=infra/momentum-public-mcp apply release.tfplan
terraform -chdir=infra/momentum-public-mcp output -raw service_url
```

Before claiming delivery, call `server/discover`, `tools/list` and all five
consultation tools **without prior initialize, cookies or session headers**
from outside GCP. Fetch an actual analysis ID before `get_analysis`, inspect
`isError` and financial/report fields, not just health/HTTP 200. Verify both
private reader URLs still reject an unauthenticated request.

The recovered suggestion routes run in Momentum API using its existing pool and
isolated `_suggestions` schema. Both tools target that same API; the MCP has no
storage credentials. To explicitly test a pending submission after deployment:

```sh
cd apps/backend/momentum-public-mcp
uv run --frozen python scripts/verify_live.py "$MCP_URL" --suggestion-symbol MCPTEST-UNIQUE
```

This creates a durable record marked as a test and checks status and deduplication.
Without the flag, the script only reads data. Confirm the record independently in
PostgreSQL before claiming durable persistence.

For an ADC reauthentication error, refresh local Application Default Credentials
or supply an ephemeral `GOOGLE_OAUTH_ACCESS_TOKEN` from the existing gcloud
identity to Terraform. Never print tokens or put them in HCL, plans or files.

Offline validation uses `terraform init -backend=false -lockfile=readonly`,
`terraform validate` and `terraform test` in a separate checkout/directory when
the root has already been initialized against the live backend.
