# Market Scanner infrastructure

This Terraform root manages the private Scanner Cloud Run service, its service
account and permissions, the daily Cloud Scheduler request at 07:00 Europe/Paris,
and the Cloud Run Job that executes each scan. The consultation API has its own
[reader root](../reader/README.md). See the [infrastructure index](../README.md)
for shared prerequisites and repository hygiene.

## Validation

Use Terraform 1.9 or later, below 2.0. From the repository root in a clean checkout:

```sh
terraform -chdir=infra/market-scanner fmt -check
terraform -chdir=infra/market-scanner init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/market-scanner validate
terraform -chdir=infra/market-scanner test
```

These tests use mock providers and verify configuration, not GCP access or database
persistence. Use a separate checkout if this root already has a live backend.

## Moving an existing checkout

This directory replaces the former Scanner root at `infra/`. Its GCS bucket,
`preprod/runtime` prefix, workspace, resource addresses and provider lock remain
the same. The approved scope is recorded in [spec PR #138](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/138).

Before updating an existing checkout, record its selected workspace, state lineage
and `terraform state list` privately. Confirm which ignored release inputs describe
the current deployment; an old image digest or secret version can propose a rollback.
Run a full baseline plan with those inputs. Keep deployments serialized throughout
the comparison.

Copy only the required ignored `config/release.local.tfvars` into this root with
mode 0600. Leave `.terraform/`, state files, plans and diagnostic logs behind.
Use a clean checkout for this operational check, separate from mock tests:

```sh
terraform -chdir=infra/market-scanner init -input=false -lockfile=readonly -backend-config=config/preprod.backend.hcl
terraform -chdir=infra/market-scanner workspace show
# If different, select the previously recorded workspace before reading state.
# Do not create a workspace if the expected one is missing.
terraform -chdir=infra/market-scanner state list
terraform -chdir=infra/market-scanner plan -input=false -detailed-exitcode -var-file=config/preprod.tfvars -var-file=config/release.local.tfvars
```

The state lineage and resource inventory must match the baseline. State snapshots
can contain private data: capture any `terraform state pull` output only into a
protected file outside Git. The full refreshed plan must exit 0 (no changes).
Exit 1 is an error; exit 2 requires investigating drift or stale inputs against
the old root. Do not apply those changes as part of relocation. No state migration,
import, `moved` block, resource renaming or module wrapper is needed.

Rollback is a revert of the directory and consumer changes, followed by fresh
initialization of the original root with the same backend/workspace and a full
plan. Do not restore state or reuse saved plans merely to reverse this move.
The infrastructure parent directory now holds shared documentation and exclusions;
it must not be used as a second Scanner root.

## Deploying to your project

The checked-in `preprod` files describe the maintainer's environment. Supply your
own project ID and backend bucket rather than applying them to another project.
Authenticate Terraform with Application Default Credentials first.

Paths in the numbered steps are relative to this directory. Shell commands run
from the repository root. Apply [database migrations](../../database/README.md)
before starting the scanner.

1. Initialize `../bootstrap/` with local state and plan/apply it using your project
   variables. Copy `../bootstrap/backend.remote.tf.example` to
   `../bootstrap/backend.remote.tf`, then use `terraform init -migrate-state` with
   your backend configuration. Keep local state out of Git.
2. Add the writer database URL as a Secret Manager version of
   `market-scanner-database-url`. Retain its numeric version.
3. Build the application Dockerfile for `linux/amd64`, publish it to the
   bootstrapped `market-scanner` repository, and resolve its immutable digest.
   The optional [image publication workflow](../../docs/adk-litellm.md#image-publication)
   automates this step after the scanner checks pass.
4. Copy `config/release.local.tfvars.example` to `config/release.local.tfvars`.
   Set the image digest, numeric database secret version, explicit invoker identities,
   and required `litellm_gateway` object. Provision its scanner key and access grant
   in `../litellm/` first; see [ADK integration](../../docs/adk-litellm.md).
5. Initialize and review a runtime plan before applying:

```sh
terraform -chdir=infra/market-scanner init -backend-config=config/preprod.backend.hcl
terraform -chdir=infra/market-scanner plan \
  -var-file=config/preprod.tfvars \
  -var-file=config/release.local.tfvars \
  -out=release.tfplan
terraform -chdir=infra/market-scanner apply release.tfplan
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
