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

### Optional existing Aiven service

`scripts/bootstrap_aiven.py` creates a dedicated `litellm` user/database in an
existing service, checks TLS and SQL writes, and uploads credentials without
printing them. It requires an authenticated Aiven CLI administrator and these
explicit environment variables:

| Variable | Value |
| --- | --- |
| `LITELLM_GCP_ACCOUNT` | Authorized gcloud account |
| `GOOGLE_CLOUD_PROJECT` | Target GCP project ID |
| `LITELLM_AIVEN_ACCOUNT` | Expected Aiven account email |
| `LITELLM_AIVEN_PROJECT` | Existing Aiven project |
| `LITELLM_AIVEN_SERVICE` | Existing PostgreSQL service |
| `LITELLM_AIVEN_HOST` | Expected PostgreSQL hostname |

```sh
uv run --project apps/backend/market-scanner-adk --no-sync python infra/litellm/scripts/bootstrap_aiven.py
```

The script preserves existing enabled secrets and the local release file. It
sets the database role's connection limit to five. Increase capacity before
running the second proxy alongside rolling updates or migrations.

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

Optional `client_service_accounts` grants existing project service accounts IAP
access, permission to sign as themselves, and access to their own virtual-key
secret. `client_operator_members` grants explicit operators impersonation rights.
These maps are empty in the public example.

To bootstrap the Scanner-named inference key, configure that existing identity
in Terraform, apply the grants, then set `LITELLM_GCP_ACCOUNT`,
`GOOGLE_CLOUD_PROJECT` and `LITELLM_BASE_URL` (the admin service's HTTPS origin):

```sh
uv run --project apps/backend/market-scanner-adk --no-sync python infra/litellm/scripts/bootstrap_scanner_key.py
```

The key allows only native `/v1beta/models/*` inference for the script's explicit
model list. Align that list with your Terraform catalog before running. Limits
are 10 requests/minute, 100,000 tokens/minute, two concurrent requests, a $10
30-day accounting budget and 30-day expiry. Existing enabled secret versions are
reused; an enabled version does not prove its virtual key is unexpired. Rotate
explicitly before expiry and revoke the old key only after testing its replacement.

The prepared `gateway.tf` also creates an internal-only service, a VPC, a subnet
with Private Google Access, and private `run.app` DNS. The gateway uses virtual
keys without IAP or Cloud Run IAM checks; internal network ingress is its
additional boundary. The admin endpoint retains IAP. Clients must route traffic
through the VPC. The merged Scanner does not include this integration and keeps
its direct Vertex permissions.

Both services share the image, config, database and runtime identity. The gateway
keeps one instance running; the admin service can scale to zero. Each has a
two-connection pool. Size PostgreSQL for both services, revision overlap and
migrations before applying this topology. There is no Redis: budgets and rate
limits are approximate/process-local and can overshoot or reset on restart.

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
credentials. The opt-in native test requires the same deployment variables as
key bootstrap and makes billable calls:

```sh
uv run --project apps/backend/market-scanner-adk --no-sync python infra/litellm/tests/scanner_native.py
```

This checks IAP denial, key restrictions, native schema/thinking, Search grounding
and streaming through the admin endpoint. It does not validate private gateway
networking or Scanner integration. Check anonymous denial, authorized browser
login, real model inference and usage persistence separately after deployment.

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
