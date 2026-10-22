# Spec: dedicated Market Scanner Terraform root

Status: proposed for review. This PR specifies the change; implementation follows
spec approval. Reviewed baseline: `origin/main` at `7949165` (2026-10-22).

## Objective

Give the Market Scanner runtime a dedicated `infra/market-scanner/` directory,
consistent with `infra/momentum/`, `infra/reader/` and `infra/litellm/`. Operators
must be able to discover, validate and plan the Scanner stack from that directory
without changing its deployed resources or remote Terraform state.

The scope is a filesystem and tooling refactor. The Scanner HTTP service, scan
job, schedule, IAM, variables, outputs and deployment inputs retain their behavior.
The consultation API remains owned by `infra/reader/`.

## Current evidence and affected consumers

| Current source | Required outcome |
| --- | --- |
| `infra/market_scanner.tf`, `market_scanner_job.tf`, `market_scanner_schedule.tf`, `market_scanner_iam.tf` | Relocate all four runtime files together. |
| `infra/backend.tf`, `variables.tf`, `outputs.tf`, `.terraform.lock.hcl` | Relocate the root configuration and preserve provider selections. |
| `infra/config/`, `infra/tests/runtime.tftest.hcl` | Relocate tracked inputs, input example and mock-provider tests. |
| `infra/README.md` | Retain an infrastructure index; extract Scanner operations into the new root's README. |
| `.github/workflows/scanner.yml` | Run Scanner init, validate and test in the new root; retain bootstrap validation and existing checks. |
| `.github/dependabot.yml`, `.github/DEPENDABOT.md` | Replace the Scanner Terraform directory `/infra` with `/infra/market-scanner`. |
| `docs/migrations/domain-databases/operations.md` | Update executable Scanner plan/apply examples. |
| `docs/migrations/domain-databases/release-map.md` | Update the Scanner owner path while retaining its state prefix. |
| `infra/.gitignore` | Keep shared exclusion rules inherited by every child stack. |

Search all tracked scripts, workflows and documentation again at implementation
time. The baseline has no Scanner-root command in `scripts/`; do not invent a
wrapper solely for this move. Historical evidence such as
`docs/migrations/domain-databases/local-evidence.md` may retain dated old paths.
Mark historical references clearly rather than rewriting past execution evidence.

## Target structure

```text
infra/
  README.md                   # Index of independent Terraform roots
  .gitignore                  # Shared local-artifact exclusions
  market-scanner/
    README.md                 # Scanner validation, deployment and relocation guide
    backend.tf
    variables.tf
    outputs.tf
    market_scanner.tf
    market_scanner_job.tf
    market_scanner_schedule.tf
    market_scanner_iam.tf
    .terraform.lock.hcl
    config/
      preprod.backend.hcl
      preprod.tfvars
      release.local.tfvars.example
    tests/runtime.tftest.hcl
  bootstrap/                  # Existing independent roots remain siblings
  frontend/
  litellm/
  momentum/
  reader/
```

Move only tracked Scanner files. Privately copy any required ignored release
inputs into the new `config/` directory, preserving restrictive permissions.
Do not copy `.terraform/`, state files, saved plans or diagnostic logs. The old
`infra/` directory must cease to be an executable Scanner Terraform root; do not
leave a duplicate configuration or a module wrapper there.

## Terraform identity and compatibility contract

1. Preserve the GCS backend type and the complete backend configuration. In the
   checked-in environment, the prefix remains `preprod/runtime`; retain the
   existing bucket and selected Terraform workspace as well. The directory name
   is not a reason to create a new state prefix.
2. Preserve resource addresses, including `google_cloud_run_v2_service.scanner`
   and `google_cloud_run_v2_job.daily_scan`, instance keys, provider bindings,
   inputs and outputs. Do not introduce `module.market_scanner` or rename labels.
3. Preserve image digests, secret version references, resource names, IAM,
   schedule/timezone, service accounts, networking and lifecycle settings.
4. Keep the provider lock file byte-for-byte and retain Terraform's existing
   `>= 1.9, < 2.0` constraint. No provider upgrade belongs in this refactor.
5. Reinitialize from a clean directory against the existing backend. No `moved`
   block, import, `state mv`, `state push` or `init -migrate-state` is required for
   this directory-only relocation. Stop if Terraform proposes a state migration.

GCS identifies state through the configured bucket, prefix and workspace. See the
[GCS backend reference](https://developer.hashicorp.com/terraform/language/backend/gcs).
Initialization and reconfiguration behavior is documented in the
[`terraform init` reference](https://developer.hashicorp.com/terraform/cli/commands/init).

## CI, documentation and style

Update the Scanner init/validate/test commands to the new root in the same
implementation PR as the move. Preserve the workflow's current `infra/**` trigger
coverage and recursive formatting check; narrowing triggers is a separate change.
Keep bootstrap checks. Update Dependabot's directory without changing its schedule.

The infrastructure index must list the roots present at implementation time,
including Momentum and frontend/build, and link to each available deployment guide.
Fix relative links when extracting the Scanner README: sibling roots gain `../`
and repository-level `docs/` or `database/` links gain an extra directory level.
Audit script path assumptions, `working-directory`, `-chdir`, relative file reads,
root validation loops and documentation links throughout the repository.

Use existing HCL formatting and resource labels. For example, retain this address:

```hcl
resource "google_cloud_run_v2_job" "daily_scan" {
  # Existing configuration is relocated without semantic edits.
}
```

## Verification commands and strategy

Run from the repository root in a clean implementation checkout. These are future
acceptance commands, not claims that the proposed directory already exists.

```sh
terraform fmt -check -recursive infra
terraform -chdir=infra/market-scanner init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/market-scanner validate
terraform -chdir=infra/market-scanner test
terraform -chdir=infra/bootstrap init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/bootstrap test
git diff --check
git diff --find-renames --stat
git grep -n -E 'chdir=infra([[:space:]]|$)|infra/(config|tests|market_scanner)' -- .
```

Review every search hit: active commands must use the new path; the spec's before
inventory and clearly dated evidence may retain old paths. Also inspect structured
YAML values for `/infra`, root arrays and working directories. Validate workflow
syntax with the repository's available tooling. Existing mock-provider tests must
pass with the same assertions; no tests may be removed to accommodate the move.
Check that shared ignore rules still exclude local inputs and Terraform artifacts.

For operational verification, use the same credentials, release inputs, provider
lock and Terraform workspace before and after the move. Record the original
workspace and state address inventory privately. Avoid concurrent deployments.
In a separate clean checkout with the required ignored release inputs provisioned:

```sh
terraform -chdir=infra/market-scanner init -input=false -lockfile=readonly -backend-config=config/preprod.backend.hcl
terraform -chdir=infra/market-scanner workspace show
terraform -chdir=infra/market-scanner state list
terraform -chdir=infra/market-scanner plan -input=false -detailed-exitcode -var-file=config/preprod.tfvars -var-file=config/release.local.tfvars
```

Select the previously recorded workspace if it differs before reading state or
planning. Compare the address inventory and state lineage to the original root;
keep raw state private. Never create a workspace to resolve an unexpected absence.
The full refreshed plan must report no changes (exit 0). Exit 1 is a failure;
exit 2 requires investigating drift or input differences against the original root,
not applying them as part of this refactor. Do not use `-target` or `-refresh=false`
as substitute proof. Mock tests establish configuration validity, not live identity.
If cloud access is unavailable, report this operational gate as unverified.

## Boundaries and rollback

- Always preserve backend identity, addresses and runtime behavior; update all
  active consumers together and review rename-aware diffs.
- Ask before expanding scope to provider upgrades, resource changes or deployment.
  This spec PR authorizes no Terraform apply or cloud mutation.
- Never commit private inputs, credentials, state or saved plans; never maintain
  two active Scanner roots or repair this move through state manipulation.

Rollback consists of reverting the implementation's file and consumer changes,
reinitializing the original root against the same backend/workspace, and checking
the full plan again. No state restoration is expected because relocation does
not modify state or resources. Do not reuse pre-move saved plans.

## Acceptance criteria

- [ ] All tracked Scanner root files, config and tests reside in `infra/market-scanner/`.
- [ ] `infra/` contains shared documentation/exclusions and sibling roots, with no Scanner root configuration left behind.
- [ ] Backend config, resource addresses, provider lock, variables and outputs are preserved.
- [ ] CI, Dependabot, active scripts and operational docs resolve the new location.
- [ ] Relative Markdown links resolve, historical evidence stays identifiable, and local artifacts remain ignored.
- [ ] Formatting, validation, existing mock tests and applicable PR checks pass.
- [ ] Operational evidence verifies the original state/workspace and a full no-change plan before the relocated root is used for deployments.

The current deliverable is this reviewable specification. The directory move and
its acceptance evidence belong to the subsequent implementation PR.
