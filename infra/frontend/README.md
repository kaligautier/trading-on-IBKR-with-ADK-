# DeepCopy frontend migration

This directory makes the frontend build and Cloud Run deployment reproducible in
`preprod-deep-copy`. It does not apply infrastructure in CI, delete Demo ADK, or
change the application source. Two independent Terraform states avoid requiring
an image before provisioning the image builder:

- `build/`: Cloud Build API, dedicated builder identity, source bucket, log writes,
  and image publication rights on the existing `market-scanner` repository.
- This root: public `deepcopy-front`, runtime identity, invocation rights on the
  existing private `market-scanner-api`, and optional frontend domain takeover.

The runtime identity has no database, Secret Manager, model, or image publication
permissions. The image must live in the destination registry so deleting the old
project cannot remove the deployed artifact. Cloud Run's invoker check is disabled
only for the public frontend; the reader continues to enforce IAM.

`preprod.tfvars` records the deployed image digest and desired domain mappings.
Both backend configurations are versioned. Reconcile the live release without
any local variable file:

```sh
terraform -chdir=infra/frontend init -backend-config=preprod.backend.hcl
terraform -chdir=infra/frontend plan -var-file=preprod.tfvars -out=frontend.tfplan
terraform -chdir=infra/frontend apply frontend.tfplan
```

Image updates and domain changes belong in reviewed changes to `preprod.tfvars`.
The following sections describe initial provisioning and subsequent image builds.

## Prerequisites

Apply `infra/bootstrap` and `infra/reader` first. They own the state bucket,
registry, existing APIs and reader; do not recreate them here. Use Terraform 1.14.4
for the same checks as CI and authenticate with Application Default Credentials.
The operator needs resource administration and IAM grant permissions for these
roots, permission to submit Cloud Builds and act as the builder, and permission
to upload source to its bucket. These personal/operator permissions are not
granted by this root.

## Build infrastructure, then build an image

All commands below run from the repository root. Review each saved Terraform
plan before applying it. Each root has a distinct backend prefix.

```sh
terraform -chdir=infra/frontend/build init \
  -backend-config=preprod.backend.hcl
terraform -chdir=infra/frontend/build plan -out=build.tfplan
terraform -chdir=infra/frontend/build apply build.tfplan

gcloud builds submit . \
  --project=preprod-deep-copy --region=europe-west1 \
  --config=infra/frontend/cloudbuild.yaml \
  --ignore-file=infra/frontend/gcloudignore \
  --service-account=projects/preprod-deep-copy/serviceAccounts/deepcopy-front-builder@preprod-deep-copy.iam.gserviceaccount.com \
  --gcs-source-staging-dir=gs://preprod-deep-copy-front-build-sources/source \
  --format='value(results.images[0].digest)'
```

The allowlist uploads only frontend source and build files. Never submit the
whole repository without it. Builds run with the dedicated identity rather than
default compute permissions. Cloud Build builds Linux images on its x86 workers;
the multi-stage Dockerfile runs the Next.js standalone server as `node`, listening
on `0.0.0.0:3000`. Backend access is configured only at runtime. No secrets or
backend access are required to compile the landing.

Update the image in checked-in `infra/frontend/preprod.tfvars` with the resulting
`sha256:...` digest and review that change before deploying it. Never reuse a
mutable tag or a digest from Demo ADK.

For the first deployment only, stage without domains using a command-line
override as shown below. The variable defaults to false for unconfigured
environments, while the versioned preprod configuration preserves the live domains.

## Stage the new service

Skip this section when reconciling an already deployed release: disabling its
domain mappings is intentionally blocked by `prevent_destroy`.

```sh
terraform -chdir=infra/frontend init \
  -backend-config=preprod.backend.hcl
terraform -chdir=infra/frontend plan \
  -var-file=preprod.tfvars -var=enable_domain_mappings=false -out=frontend.tfplan
terraform -chdir=infra/frontend apply frontend.tfplan
terraform -chdir=infra/frontend output -raw service_url
```

At this stage the old website still serves `deepcopy.fr`. Check the new `run.app`
URL in a browser: landing, latest scanner report, links, and mobile layout.
Compare its report with the reader. A successful HTTP response alone does not
prove the private reader integration. Confirm an unauthenticated request to the
reader is still rejected. CI validates with mock providers and boots the image;
it does not prove IAM, live report access or ownership of the public domains.

## Transfer the frontend domains in a second reviewed plan

The account applying the mapping must own/verify `deepcopy.fr` with Google.
Preserve the existing Squarespace verification TXT. If Google requires another
verification token, add it there; tokens and domain ownership are account setup
prerequisites, not secrets to commit to this repository.

After validating the staged service, use the versioned preprod configuration
without the staging override and generate/review/apply another saved plan using
the reconciliation commands at the top of this document. It creates mappings
for `deepcopy.fr` and `www.deepcopy.fr`, with
`force_override = true`, transferring routing from Demo ADK to the new service.
Google manages the HTTPS certificates. Provisioning can cause an interruption;
keep the old project available until HTTPS and real reader access work through
both domains. `www` serves the same app; this mapping does not create a redirect.

Compare `terraform output domain_resource_records` with the existing Squarespace
A/AAAA records and `www` CNAME. The existing Google targets should be reusable;
do not change them unless the returned required records differ. No Squarespace
DNS or registrar changes are performed by these roots. Cloud DNS resources would
not manage the authoritative Squarespace zone.

Once mappings exist, keep the flag true: `prevent_destroy` intentionally blocks
removing them, including toggling the flag off. Service deletion is also
protected. To roll back an application release, restore the previous destination
image digest in `preprod.tfvars` and apply a reviewed plan; no domain change is required.

**Demo ADK retirement is separate.** `mcp.deepcopy.fr` is excluded. Its existing
mapping must be resolved, and the old project's other resources and dependencies
inventoried, before project deletion. This PR does not make deleting Demo ADK safe
by itself and never manages that project's lifecycle.

## Offline checks

```sh
terraform -chdir=infra/frontend fmt -check -recursive
terraform -chdir=infra/frontend init -backend=false -lockfile=readonly
terraform -chdir=infra/frontend validate
terraform -chdir=infra/frontend test
terraform -chdir=infra/frontend/build init -backend=false -lockfile=readonly
terraform -chdir=infra/frontend/build validate
docker build -f infra/frontend/Dockerfile -t local/deepcopy-front:review .
```

References: [Cloud Run domain mapping](https://docs.cloud.google.com/run/docs/mapping-custom-domains),
[Terraform mapping resource](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_domain_mapping),
[Cloud Build user identities](https://docs.cloud.google.com/build/docs/securing-builds/configure-user-specified-service-accounts).
