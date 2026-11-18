# Private Momentum consultation service

Independent Terraform root/state. Deploys one `momentum-api` service account,
a Cloud Run service with enforced IAM and named invokers, and access to exactly
the existing reader database URL and CA secrets. No database/password/key is
created or read into Terraform state. No anonymous invoker is permitted.

Prerequisites: existing registry and enabled GCP APIs, reader migration/bootstrap,
a published API image digest, and numeric reader-URL/CA Secret Manager versions.
The URL uses `momentum_results_reader`, database `momentum`, `sslmode=verify-full`
and `sslrootcert=/etc/database/ca.pem`. Never put the URL in Terraform values.

```sh
terraform init -backend-config=bucket=YOUR_STATE_BUCKET \
  -backend-config=prefix=momentum-api
terraform plan -var=project_id=YOUR_PROJECT \
  -var=image=REGISTRY/momentum-api@sha256:DIGEST \
  -var=database_secret_version=1 -var=ca_secret_version=1 \
  -var='invoker_members=["serviceAccount:YOUR_CALLER@YOUR_PROJECT.iam.gserviceaccount.com"]'
```

Use a dedicated `momentum-api` state prefix. Review the saved plan before applying.
Each process has a pool of one, each revision has at most one requested instance,
and the reader role enforces a one-connection ceiling, so avoid revision overlap.
Cloud Run instance ceilings can be temporarily exceeded by the platform; database
role limits remain authoritative. Deployments must respect that connection budget.
The service sets AUTH_MODE=cloud_run and relies on Google's audience-bound IAM
verification at ingress. Never disable the invoker IAM check or expose its
container outside that boundary. A future MCP gets invocation rights only.

The existing preproduction target and its deployed release values (image digest,
secret versions) are checked in under `config/preprod.tfvars` and
`config/preprod.backend.hcl`; update them in the same change as each deployment.
Personal invoker identities stay in ignored `config/identities.local.tfvars`
(`invoker_members = [...]`), because this repository is public. Use those same
files for plan and apply:

```sh
terraform init -backend-config=config/preprod.backend.hcl -lockfile=readonly
terraform plan -var-file=config/preprod.tfvars \
  -var-file=config/identities.local.tfvars -out=release.tfplan
terraform apply release.tfplan
```

```sh
terraform fmt -check -recursive
terraform init -backend=false -input=false -lockfile=readonly
terraform validate
terraform test
```

Tests mock the provider and do not deploy resources. Publication, migration,
reviewed apply, live denied/allowed identity checks and an independent comparison
of retained financial values are separate release gates. No live release is
claimed by these local checks. TLS/HTTP negotiation at managed ingress must be
verified independently of the container's HTTP/1.1 tests.


The suggestion routes use the existing database pool. `suggestion_key_version`
pins the `momentum-mcp-caller-key` secret version shared with the public MCP;
it adds only an accessor grant and secret-backed environment variable. The
2026-10-24 release image and numeric secret versions are recorded in
`config/preprod.tfvars`; preserve the existing private invoker list when planning.
The build definition is `cloudbuild.yaml` (BuildKit required by the Dockerfile).

## Secret containers

Terraform manages the containers of the reader URL and CA secrets (`secrets.tf`);
their values are still uploaded outside Terraform. A project that already holds them
adopts them on the first apply only:

```sh
terraform plan -var-file=config/preprod.tfvars -var-file=config/identities.local.tfvars \
  -var=adopt_existing_secrets=true
```

The plan reports `2 to import, 0 to add, 2 to change, 0 to destroy`; the two changes
only record the existing `application` and `component` labels in state. Later plans
omit the flag.
