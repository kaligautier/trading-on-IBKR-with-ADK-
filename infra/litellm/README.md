# LiteLLM on Cloud Run

Deploy the official LiteLLM proxy and admin UI behind Google IAP, using Vertex AI
with an attached service account and a dedicated PostgreSQL database. Optional
OpenAI, Anthropic and Gemini API providers use Secret Manager references.

This Terraform stack owns a separate state prefix. The Scanner uses Vertex
independently; this stack does not change its application, scheduler or IAM.

## Configuration

Requirements: Terraform >= 1.9, gcloud, an existing GCS state bucket, and the
shared `infra/bootstrap` APIs. Use a dedicated PostgreSQL database/user with DDL
rights only in that database. LiteLLM owns its Prisma schema, not Liquibase.

```sh
cp infra/litellm/config/preprod.backend.hcl.example infra/litellm/config/preprod.backend.local.hcl
cp infra/litellm/config/preprod.tfvars.example infra/litellm/config/preprod.local.tfvars
cp infra/litellm/config/release.local.tfvars.example infra/litellm/config/release.local.tfvars
```

Fill the local files with your state bucket, project, allowed IAP principals and
numeric secret versions. Verify model availability in your project and region.
Local configuration, state, plans, credentials and OAuth downloads must stay out
of Git. Examples contain placeholders only. Never put secret values in tfvars:
Terraform manages secret containers and references, not credential payloads.

The pinned proxy and migration images use the same upstream version. Artifact
Registry mirrors GHCR because Cloud Run cannot pull GHCR references directly.

## Database and secrets

Create the foundation with the local backend and project configuration:

```sh
terraform -chdir=infra/litellm init -backend-config=config/preprod.backend.local.hcl
terraform -chdir=infra/litellm plan -var-file=config/preprod.local.tfvars -out=foundation.tfplan
terraform -chdir=infra/litellm apply foundation.tfplan
```

Upload these credentials from protected files with `gcloud secrets versions add
SECRET --project=YOUR_PROJECT --data-file=/PROTECTED_PATH/value`:

- `litellm-database-url`: dedicated PostgreSQL connection URL.
- `litellm-master-key`: random administrator API key beginning with `sk-`.
- `litellm-salt-key`: independent random encryption key; keep it stable.
- `litellm-ui-password`: random admin password.
- `litellm-database-ca`: custom CA, when required by the database.

For a custom CA, the database URL uses Prisma's verified TLS options:

```text
postgresql://USER:PASSWORD@HOST:PORT/litellm?sslmode=require&sslcert=/etc/database/ca.pem&sslaccept=strict&connection_limit=2
```

URL-encode credentials. Record only the returned numeric secret versions in
`release.local.tfvars`. Changing the salt makes stored provider credentials
unreadable. Back up the database before upgrades.

### Existing PostgreSQL database

For an existing Aiven service, prefer a protected administrator connection file
and the downloaded project CA. The file contains `{"url":"POSTGRES_ADMIN_URI"}`;
restrict it to `0600` and keep it outside Git. Use the existing dedicated
`litellm` database and role; no new database service is required.

```sh
uv run --project apps/backend/market-scanner-adk --no-sync python infra/litellm/scripts/bootstrap_database.py \
  --admin-file=/PROTECTED_PATH/admin.json --ca-file=/PROTECTED_PATH/ca.pem \
  --expected-host=YOUR_DATABASE_HOST --project=YOUR_PROJECT --account=YOUR_ACCOUNT
```

The script preserves existing enabled secret versions, checks role privileges,
verifies TLS and SQL writes, and sets the dedicated role's connection limit to
12 by default. If existing encrypted records have no recoverable salt, it stops
instead of creating an incompatible salt. Check the service's total connection
capacity before choosing the limit. Remove the temporary administrator file
once bootstrap is complete.

The optional `bootstrap_aiven.py` also supports an authenticated Aiven CLI via
explicit `LITELLM_GCP_ACCOUNT`, `GOOGLE_CLOUD_PROJECT`, `LITELLM_AIVEN_ACCOUNT`,
`LITELLM_AIVEN_PROJECT`, `LITELLM_AIVEN_SERVICE` and `LITELLM_AIVEN_HOST` variables.

## Migrations, service and IAP

Apply migrations before exposing the service:

```sh
terraform -chdir=infra/litellm plan -var-file=config/preprod.local.tfvars \
  -var-file=config/release.local.tfvars -var=stage=migrations -out=migrations.tfplan
terraform -chdir=infra/litellm apply migrations.tfplan
gcloud run jobs execute litellm-migrations --wait --project=YOUR_PROJECT --region=europe-west1
terraform -chdir=infra/litellm plan -var-file=config/preprod.local.tfvars \
  -var-file=config/release.local.tfvars -var=stage=service -out=service.tfplan
terraform -chdir=infra/litellm apply service.tfplan
terraform -chdir=infra/litellm output -raw ui_url
```

After deployment, set `stage = "service"` in the local release file and always
include it in subsequent plans. Returning to an earlier stage proposes service
deletion; deletion protection blocks it. Regenerate plans after code changes.
Never apply a saved plan from a previous checkout.

IAP protects the admin service, including its `run.app` URL. Cloud Run IAM checks
remain enabled; only the IAP service agent gets invocation access. Allowlisted
users still sign in to LiteLLM as `admin` with the separate UI password. IAP
does not create LiteLLM users. Keep the bootstrap login until a named admin has
been created and tested, then consider `disable_env_credential_login=true`.

For projects requiring a custom OAuth client, complete the Google console setup
and register `https://iap.googleapis.com/v1/oauth/clientIds/CLIENT_ID:handleRedirect`.
Keep the downloaded client JSON outside the repository, restrict its permissions,
and attach it with explicit project identity:

```sh
python3 infra/litellm/scripts/configure_iap_oauth.py /PROTECTED_PATH/client.json \
  --project=YOUR_PROJECT --project-number=YOUR_PROJECT_NUMBER --account=YOUR_ACCOUNT
```

This updates project-level IAP OAuth credentials, preserves other settings, and
refuses to replace a different client. It does not store credentials in state.

## Optional API-key providers

External providers are inactive until an exact model and numeric credential
version are configured. No wildcard model or custom upstream URL is accepted.

```sh
python3 infra/litellm/scripts/upload_provider_key.py openai \
  --project=YOUR_PROJECT --account=YOUR_ACCOUNT
cp infra/litellm/config/providers.local.tfvars.example infra/litellm/config/providers.local.tfvars
```

The key is entered through a hidden terminal prompt and uploaded over stdin.
Other provider choices are `anthropic` and `gemini`. Fill the local provider
file with the returned version and an exact available model ID, then include
`-var-file=config/providers.local.tfvars` with both other variable files in all
subsequent plans. Test inference and accounting after deployment. Provider
credentials and models added through the admin UI persist in PostgreSQL; UI
settings can override YAML. Avoid duplicating a YAML alias in the UI.

## Application access and private gateway

`client_service_accounts` grants existing project identities access only to
their own virtual-key secret. Agents have no IAP access or token-signing grant.
They call the private gateway using `Authorization: Bearer <virtual-key>`.

The gateway is internal-only, with a VPC, Private Google Access and private
`run.app` DNS. Cloud Run agents must attach to the supplied subnet and route
this traffic through the VPC. The admin endpoint retains IAP plus LiteLLM login.
The current Scanner application still uses Vertex directly; its dedicated
verification job exercises the gateway with the same service account.

### Key provisioning and verification jobs

Set `client_tools_image` to a digest-pinned Python image containing `httpx`,
`google-auth`, `google-genai` and `pydantic`. The existing Scanner image has these
dependencies. The optional jobs use Direct VPC egress; no IAP authentication is
implemented in their scripts.

After applying the service stage, run `litellm-key-CLIENT_NAME`. Its dedicated
bootstrap identity can read the master secret, list its client-key versions and
add a version; it cannot read the client key back or destroy versions. It creates
an inference-only virtual key inside the VPC and uploads it directly to Secret
Manager. Credential payloads never appear in Terraform arguments or logs.

```sh
gcloud run jobs execute litellm-key-CLIENT_NAME --wait --project=YOUR_PROJECT --region=europe-west1
```

Pin the returned numeric version in the ignored configuration:

```hcl
client_key_versions = { CLIENT_NAME = "1" }
```

Reapply and run `litellm-verify-CLIENT_NAME`. The verification identity is the
agent SA, with only its own key mounted, and the job calls the internal endpoint
with no IAP or Google identity token.

Keys permit `/v1beta/models/*` and the configured model catalog. Limits are
10 requests/minute, 100,000 tokens/minute, two concurrent requests, a $10 30-day
accounting budget and 30-day expiry. Bootstrap reruns preserve existing enabled
versions; they do not prove the key is unexpired or perform rotation. Rotate
explicitly and verify the replacement before revoking the old key.

Both services share the image, config, database and runtime identity. Each uses
a two-connection pool; size PostgreSQL for revision overlap and migrations.
There is no Redis: rate limits are process-local, counters may reset, and
asynchronous accounting can overshoot budgets.

## Verification and upgrades

```sh
terraform -chdir=infra/litellm fmt -check
terraform -chdir=infra/litellm validate
terraform -chdir=infra/litellm test
uv run --project apps/backend/market-scanner-adk --no-sync pytest -c /dev/null infra/litellm/tests/test_configuration.py
python3 infra/litellm/tests/smoke.py
```

Terraform tests use mocked providers. The Docker smoke test runs the pinned
images with disposable PostgreSQL and mocked inference: migrations, UI login,
authentication, key restrictions and persistence after restart. It uses no cloud
credentials. The opt-in native test makes billable calls:

```sh
uv run --project apps/backend/market-scanner-adk --no-sync python infra/litellm/tests/scanner_native.py
```

This runs from inside the VPC with `LITELLM_BASE_URL` and the mounted
`LITELLM_API_KEY`. It checks key restrictions, native schema/thinking, Search
grounding and streaming through the private gateway without IAP. Check anonymous
denial, authorized browser login, real model inference and usage persistence
separately after deployment.

Runtime settings disable prompt/response spend-log persistence and message
logging, redact key details, and retain usage accounting. Provider timeout is
600 seconds, router timeout 170 seconds, with one transient retry and no
cross-provider fallback. These controls do not determine provider retention or
guarantee upstream errors never contain request content.

For upgrades, back up PostgreSQL, update/apply the migration image, run its job,
then update the proxy digest and deploy. Keep prior config secret versions for
rollback; database rollback depends on upstream migration compatibility.

References: [LiteLLM configuration](https://docs.litellm.ai/docs/proxy/configs),
[native Gemini API](https://docs.litellm.ai/docs/generateContent),
[production settings](https://docs.litellm.ai/docs/proxy/prod),
[Cloud Run IAP](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run),
[private networking](https://docs.cloud.google.com/run/docs/securing/private-networking).

For rebuilding after an incident, see [RECOVERY.md](RECOVERY.md).
