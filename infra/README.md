# Scanner infrastructure

Three Terraform roots manage the GCP resources:

- `bootstrap/`: APIs, protected state bucket, Artifact Registry, and database
  secret metadata. Secret values are supplied separately and never enter state.
- This directory: private Cloud Run, its service account and permissions, and
  a daily Cloud Scheduler request at 07:00 Europe/Paris, and a Cloud Run Job
  that runs the scan independently of the HTTP request.
- `litellm/`: the private inference gateway and IAP-protected admin service.

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
   Set the image digest, numeric database secret version, explicit invoker identities,
   and required `litellm_gateway` object. Provision its scanner key and access grant
   in `litellm/` first; see [ADK integration](../docs/adk-litellm.md).
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
The image must implement the LiteLLM gateway configuration in this module.
Never reuse an unrelated image digest solely because it is already deployed.

## Live verification

Check the ready service revision and job image digest, then invoke
`/internal/daily-scan` with a Cloud Run identity token from an allowed invoker.
The route submits the Cloud Run Job and returns HTTP 200 with
`{"status": "accepted", "operation": "projects/.../operations/..."}`.
This acknowledges submission, not scan completion. It returns 503 if the job
is unconfigured and 502 if submission fails. The service uses its attached
identity and `roles/run.invoker` on this job only, without execution overrides.

The job runs `python -m app.jobs.daily_scan`. It creates an ephemeral ADK session
and calls `Runner.run_async` directly; there are no internal HTTP/SSE calls.
It exits 0 only after the persistence node completes, or 1 on failure. Its
execution name identifies the stored report as `scheduled:<execution-name>`.
The session disappears when the worker exits; the report remains in PostgreSQL.
Use the returned operation to track the execution, check its final status and
`scheduled_scan.completed`/`scheduled_scan.failed` logs, then reread the report
and normalized assets/horizons through a separate database reader.

Scheduler success now confirms dispatch only. Monitor job execution failures to
detect a missing report. Scheduler and job retries are disabled; manually
repeating a request creates another execution. Parallelism 1 applies within one
execution, not across several executions; avoid overlapping manual runs with the
small database connection budget. This is not an exactly-once queue.

For local worker validation, configure a reachable LiteLLM gateway, its virtual
key and the database, then run
`uv run python -m app.jobs.daily_scan` from the scanner directory. The HTTP
trigger requires `MARKET_SCANNER_JOB=projects/PROJECT/locations/REGION/jobs/JOB`
and permission to invoke it; it does not silently run an in-process background
scan when the job is absent.
