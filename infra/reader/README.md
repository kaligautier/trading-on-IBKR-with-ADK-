# Private consultation service

Independent Terraform root for `market-scanner-api`. It consumes an existing
registry and two existing Secret Manager secrets. It does not change the writer,
its Cloud Run Job, scheduling, LiteLLM, or PostgreSQL objects. Keep its Terraform
state under a **separate backend prefix**, such as `market-scanner/reader`.

Prerequisites:

1. Build/push the API image and resolve its immutable digest.
2. Provision a reader URL secret named `market-scanner-reader-database-url`, using
   `market_scanner_reader` and the existing `market_scanner` schema. Its URL must
   include `sslmode=verify-full&sslrootcert=/etc/database/ca.pem`.
3. Provision the public Aiven project CA as `market-scanner-database-ca`, or set
   `ca_secret_id` to the existing CA secret for the same Aiven project.
4. Pin numeric versions for both secrets. Never pass secret payloads to Terraform.
5. Set explicit caller identities in `invoker_members` (usually a frontend/backend
   service account). Empty means no callers are granted by this root.

Create ignored `release.local.tfvars` with `project_id`, `region`, `image`,
`database_secret_version`, `ca_secret_version` and `invoker_members`.
Initialize with the existing state bucket and the dedicated prefix:

```sh
terraform init -backend-config='bucket=YOUR_STATE_BUCKET' \
  -backend-config='prefix=market-scanner/reader'
terraform plan -var-file=release.local.tfvars -out=reader.tfplan
# Review the concrete plan before applying it.
terraform apply reader.tfplan
```

The service uses a dedicated service account with access to only those two
secrets, requires Cloud Run IAM invocation, and receives no model or writer
permissions. It uses one worker, one database connection per instance, minimum
zero and maximum one instance, and request-based CPU allocation. Cold starts and
revision overlap still apply; these settings are not a global spending cap.

After deployment, verify an unauthenticated request is rejected by Cloud Run,
then use an authorized caller identity token (audience = service URL) to check
`/ready`, `/market-scans/latest`, history pagination and detail. Compare the latest
report with a separate read-only SQL query. Liveness alone is not functional proof.
No live deployment or Terraform apply is performed by the PR checks.

Offline configuration checks:

```sh
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
terraform test
```
