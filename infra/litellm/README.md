# LiteLLM on Cloud Run

Deploy the official LiteLLM proxy and admin UI behind Google IAP, using Vertex AI
with an attached service account and a dedicated PostgreSQL database. Optional
OpenAI, Anthropic and Gemini API providers use Secret Manager references.

This Terraform stack owns a separate state prefix. The Scanner runtime root
connects its application and worker to the gateway configured here.

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
The current pins are LiteLLM 1.103.4; see [SECURITY.md](SECURITY.md) for the
dependency audit, its scope and the upgrade policy.

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
Both bootstrap scripts refuse to generate a replacement salt when encrypted
records already exist. Recover the original enabled salt version first.
The Aiven bootstrap also validates the retained enabled database URL against
the service host, port, dedicated user/database and current password, and compares
the retained CA with the project CA before changing the database or secrets.
A mismatch stops bootstrap. Update the connection secrets explicitly and pin
the verified numeric versions; preserve the original encryption salt. Existing
release files remain unchanged, so review their pinned versions separately.

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
Only the gateway's NGINX container receives ingress. It forwards native Gemini
generation, streaming and token-count routes, readiness/liveness, and the
master-key-protected key generation/deletion routes. Other routes, including
login, UI, SSO and administration, return 404. The proxy listens on port 4001;
it receives no UI username or password. LiteLLM still authenticates forwarded
requests. The NGINX image is pinned by `gateway_filter_digest` and mirrored
through the same Artifact Registry repository.
Keep NGINX first in the container list: the provider preserves computed ports
by list index when updating the original single-container service. Each service
scales from zero to one instance and uses request-based billing (`cpu_idle = true`).
The admin container is limited to 1 vCPU and 1 GiB; the gateway has two containers,
each limited to 1 vCPU and 512 MiB. Size memory from measured workload peaks.
Startup, shutdown and health-check probes still consume billable resources.
Request-based billing can delay background work. Verify LiteLLM's 60-second
batched spend writes after an idle interval and cold start before relying on
durable accounting. The Docker smoke does not simulate Cloud Run CPU throttling.
The Scanner application uses this gateway; see
[ADK configuration](../../docs/adk-litellm.md). Its dedicated verification job
exercises the gateway with the same service account.

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
Without `redis_connection`, rate limits are process-local and counters may reset.
Shared Redis coordinates counters across both services; asynchronous accounting
can still overshoot budgets.

Set `global_budget_usd` in the ignored release file to cap LLM spend across the
whole proxy over 30 days. LiteLLM budgets use USD; convert EUR explicitly when
setting the amount. Both services use the same budget configuration and durable
database accounting. This excludes Cloud Run and other infrastructure charges;
concurrent requests and delayed accounting can overshoot the configured limit.
In the previously tested v1.103.1 UI, the Global Usage budget card read the current
user's personal budget and could show "No limit" even when this proxy budget was
set. That UI behavior has not been revalidated on v1.103.4.
Verify the global setting through the authenticated `/global/spend` admin API;
the `litellm-proxy-budget` user row in PostgreSQL also records its maximum,
duration and next reset. Do not add an admin-user limit to change this display.

### Optional external Redis / Aiven Valkey

This stack does not provision a Redis service or Memorystore. Supply an existing
TLS endpoint to share quotas and router state across both proxies. Aiven offers
a [free Valkey plan](https://aiven.io/docs/products/valkey/concepts/valkey-free-tier)
compatible with Redis: 1 GB RAM, `maxmemory` at 50%, one node, no VPC, and possible
shutdown after inactivity. Validate your selected plan before creating it.

For a new deployment, foundation prepares `litellm-redis-password` and
`litellm-redis-ca`. For an existing deployment, keep `stage = "service"` and
retain all current variable files: first plan/apply with `redis_connection`
unset to add the secret containers. Upload the password from a protected file
using the secret upload command above, then pin only its numeric version in the
ignored release file and plan/apply again:

```hcl
redis_connection = {
  host = "YOUR_VALKEY_HOST"
  port = 12345 # Replace with the service's TLS port.
  username = "default"
  password_version = "1"
}
```

The endpoint uses normal internet egress. TLS certificate and hostname
verification are required. New Aiven Valkey services use a publicly trusted
certificate, so no CA upload is needed. If your service offers a project CA,
upload it to `litellm-redis-ca` and add its numeric `ca_version` to the object.
See [Aiven certificate requirements](https://aiven.io/docs/platform/concepts/tls-ssl-certificates).
Credential payloads remain outside Terraform state. Reapply service stage after
pinning the connection; verify both deployed proxies before relying on shared
limits. The local smoke test proves Redis behavior, not live Aiven connectivity.
For local Docker runs, an ignored root `.env` can instead contain `REDIS_URL`
using a `rediss://` URI with `?ssl_cert_reqs=required&ssl_check_hostname=true`.
Pin these TLS options in the URI: the pinned LiteLLM URL connection path filters
separate TLS environment options. Pass the file with Docker's `--env-file`. Keep the
file at permissions `0600`. Cloud Run does not load this local file: deployment
uses the Secret Manager password reference described above.

## Verification and upgrades

```sh
terraform -chdir=infra/litellm fmt -check
terraform -chdir=infra/litellm validate
terraform -chdir=infra/litellm test
uv run --project apps/backend/market-scanner-adk --no-sync pytest -c /dev/null -p no:cacheprovider infra/litellm/tests
python3 infra/litellm/tests/smoke.py
python3 infra/litellm/tests/gateway_smoke.py
python3 infra/litellm/tests/native_gateway_smoke.py
python3 infra/litellm/scripts/audit_images.py --output-dir=/tmp/litellm-audit
```

Terraform tests use mocked providers and require Terraform >= 1.14; CI pins
1.14.4. This version includes the [test cleanup fix](https://github.com/hashicorp/terraform/pull/37364)
for resources protected by `prevent_destroy`, so deployment safeguards stay enabled.
The Docker smoke test runs the pinned
images with disposable PostgreSQL and mocked inference: migrations, UI login,
authentication, key restrictions, persistence after restart, and shared RPM
limits across two proxies using authenticated Redis with verified TLS. It also
rejects an untrusted server certificate and blocks inference on both proxies
after simulated global overspend and a restart of each proxy. This budget test
modifies only its disposable local database. The gateway smoke test uses a permissive
upstream to prove NGINX blocks login/admin routes while preserving authorization
and SSE streaming. The native gateway test runs real NGINX and two pinned LiteLLM
proxies against PostgreSQL and shared Redis on an internal Docker network.
Only the Gemini provider is stubbed. It exercises the deployed native route and
virtual-key scope, shared RPM enforcement, incremental SSE frames, persisted
usage/cost and accumulation in the global budget row. After simulating overspend,
it restarts both proxies and requires both to reject native requests. Accounting
is flushed faster in this fixture; deployed limits can still overshoot as noted
above. These Docker tests use no cloud credentials or billable provider calls.
The `LiteLLM checks` workflow runs them on scoped PRs and pushes to main, together
with Terraform validation/tests, Python lint/tests and an audit of installed
Python packages in both pinned release images. A known advisory fails that audit;
inventory and JSON reports are written to the supplied output directory.

The separate opt-in live native test makes billable calls:

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
Before deployment, review upstream release notes, keep both images on the same
version, and rerun the checks above. The image audit defaults to `linux/amd64`,
the Cloud Run architecture; use `--platform=linux/arm64` for an additional local
Apple Silicon audit. Local checks do not prove a deployed revision is healthy.

References: [LiteLLM configuration](https://docs.litellm.ai/docs/proxy/configs),
[native Gemini API](https://docs.litellm.ai/docs/generateContent),
[production settings](https://docs.litellm.ai/docs/proxy/prod),
[Cloud Run IAP](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run),
[private networking](https://docs.cloud.google.com/run/docs/securing/private-networking).

For rebuilding after an incident, see [RECOVERY.md](RECOVERY.md).
