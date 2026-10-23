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
and the reader role enforces a two-connection ceiling for revision overlap.
Cloud Run instance ceilings can be temporarily exceeded by the platform; database
role limits remain authoritative. Deployments must respect that connection budget.
The service sets AUTH_MODE=cloud_run and relies on Google's audience-bound IAM
verification at ingress. Never disable the invoker IAM check or expose its
container outside that boundary. A future MCP gets invocation rights only.

The existing preproduction target is checked in under `config/preprod.tfvars`
and `config/preprod.backend.hcl`. Keep release values in ignored
`config/release.local.tfvars`; use those same files for plan and apply:

```sh
terraform init -backend-config=config/preprod.backend.hcl -lockfile=readonly
terraform plan -var-file=config/preprod.tfvars \
  -var-file=config/release.local.tfvars -out=release.tfplan
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
