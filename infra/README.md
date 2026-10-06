# Scanner infrastructure

Two Terraform roots manage the GCP resources:

- `bootstrap/`: APIs, protected state bucket, Artifact Registry, and database
  secret metadata. Secret values are supplied separately and never enter state.
- This directory: private Cloud Run, its service account and permissions, and
  a daily Cloud Scheduler request at 07:00 Europe/Paris.

The database is external to Terraform. Apply its migrations before starting the
scanner; see [database setup](../database/README.md).

## Validation

Use Terraform 1.9 or later, below 2.0. From the repository root:

```sh
terraform fmt -check -recursive infra
terraform -chdir=infra/bootstrap init -backend=false
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/bootstrap test
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
terraform -chdir=infra test
```

These tests use mock providers. They verify configuration, not GCP access or
database persistence. Use a separate checkout for offline validation if a root
is already initialized against a live backend.

## Deploying to your project

The checked-in `preprod` files describe the maintainer's environment. Supply your
own project ID and backend bucket rather than applying them to another project.
Authenticate Terraform with Application Default Credentials first.

1. Initialize `bootstrap/` with local state and plan/apply it using your project
   variables. Copy `bootstrap/backend.remote.tf.example` to
   `bootstrap/backend.remote.tf`, then use `terraform init -migrate-state` with
   your backend configuration. Keep local state out of Git.
2. Add the writer database URL as a Secret Manager version of
   `market-scanner-database-url`. Retain its numeric version.
3. Build the application Dockerfile for `linux/amd64`, publish it to the
   bootstrapped `market-scanner` repository, and resolve its immutable digest.
4. Copy `config/release.local.tfvars.example` to `config/release.local.tfvars`.
   Set the image digest, numeric secret version, and explicit invoker identities.
5. Initialize and review a runtime plan before applying:

```sh
terraform -chdir=infra init -backend-config=config/preprod.backend.hcl
terraform -chdir=infra plan \
  -var-file=config/preprod.tfvars \
  -var-file=config/release.local.tfvars \
  -out=release.tfplan
terraform -chdir=infra apply release.tfplan
```

Use your own configuration paths when deploying outside the maintainer's
environment. Plan files can contain private configuration; do not commit them.
The image must implement the direct Vertex AI configuration in this module.
Never reuse an unrelated image digest solely because it is already deployed.

## Live verification

Check the ready revision and image digest, then invoke `/internal/daily-scan`
with a Cloud Run identity token from an allowed invoker. The endpoint creates an
ADK session, runs the full graph, and requires the persistence node to complete.
It returns 503 if the database is unconfigured and 502 if the scan fails.

Record the returned `marker` and use a separate reader connection to check
`market_scanner.market_scans.session_id`. Confirm the report's schema version,
its assets, and the corresponding normalized asset/horizon rows. An HTTP 200,
a ready revision, or a successful Terraform plan alone does not prove a durable
database write. Also verify a Scheduler-triggered run to cover its OIDC identity.
