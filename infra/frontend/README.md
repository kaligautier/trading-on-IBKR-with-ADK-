# Public Cloud Run frontend

This root manages one public service, one dedicated service account and one
service-level `roles/run.invoker` grant on the existing private reader. It does not
alter the reader's authentication setting, create database access or grant project
roles. There are no static frontend secrets.

The frontend scales from zero to one instance, with one vCPU, request-based CPU
allocation and 512 MiB memory. This reduces idle cost but allows cold-start latency;
it is not a global spending cap. The application coalesces and briefly caches reads.

## Deploy

Build and test the frontend before publishing its image. Use a dedicated GCS state
prefix, separate from `infra/reader`, and an immutable image digest:

```sh
terraform init -backend-config='bucket=YOUR_STATE_BUCKET' -backend-config='prefix=preprod/frontend'
terraform plan -var='project_id=YOUR_PROJECT' -var='image=REGION-docker.pkg.dev/YOUR_PROJECT/market-scanner/market-scanner-front@sha256:DIGEST' -out=release.tfplan
terraform apply release.tfplan
terraform output -raw service_url
```

Review the plan: first deployment should create three resources and delete none.
The reader must already exist. Its actual service URL is read from Google Cloud,
used as upstream and token audience; it is never inferred from a service name.

Public access uses `invoker_iam_disabled = true` on the frontend only, following
[Google's public access documentation](https://docs.cloud.google.com/run/docs/authenticating/public).
The scoped invocation grant and metadata token follow
[service-to-service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service).

## Validate and verify

```sh
terraform fmt -check -recursive
terraform init -backend=false -input=false -lockfile=readonly
terraform validate
terraform test
```

After applying, independently verify readiness, `/health`, anonymous `/` and
`/docs`, a rendered report ID matching the authenticated reader, and denied
anonymous reader access. Check `reader_fetch` outcomes and browser CSP errors.
Do not mistake a 200 landing response for a successful reader fetch.

Rollback: restore the last known-good image digest in Terraform, inspect the plan,
apply, and repeat those checks. The deployment changes no durable market data.
