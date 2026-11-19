# Application releases from GitHub Actions

[`deploy.yml`](../../.github/workflows/deploy.yml) releases one backend image to preprod
without a laptop: it builds the image from `main`, plans the Terraform root, **refuses any
plan that is not an image update**, applies it after a reviewer approves, and pushes a
branch that pins the new digest so `main` keeps describing production.

| Root | Image | State prefix |
| --- | --- | --- |
| `market-scanner` | `market-scanner-adk` (service and daily job) | `preprod/runtime` |
| `reader` | `market-scanner-api` | `preprod/reader` |
| `momentum-api` | `momentum-api` | `preprod/momentum-api` |
| `momentum` | Momentum worker (analysis job) | `preprod/momentum` |

The table lives in [`releases.json`](releases.json). Not covered, because their releases
are not image-only: `litellm` (migrations, secrets, IAM), `momentum-public-mcp` (its own
`deploy.py` verification), `frontend` (domain mappings), `bootstrap`, `drift`, `budget-guard`
and every IAM or secret change. Those stay manual, reviewed Terraform applies.

## How a release runs

1. **Dispatch** the workflow on `main` with the root, and optionally an existing `digest`
   (to roll out or roll back without building). `dry_run` is **on by default**.
2. A reviewer approves the `preprod-deploy` environment. Only then does the job get a
   Google identity.
3. The image is built by Cloud Build as the dedicated `backend-builder` identity, and its
   digest is read from the build result. With `digest` set, the build is skipped and the
   digest must already exist in the registry.
4. Terraform plans with `-var image=<repository>@<digest>`. The tfvars files come from the
   repository plus the private plan inputs shared with the nightly drift check.
5. [`check_image_only_plan.py`](scripts/check_image_only_plan.py) reads the plan JSON and
   refuses anything except an in-place update of a Cloud Run service or job whose **only**
   difference is the image, pinned by digest in the expected repository. A secret version,
   an env var, a scaling field, a delete, a replace or any other resource fails the job.
6. With `dry_run` off, the saved plan is applied, then a second plan must be empty.
7. The `record` job pushes `release/<root>-<run id>` with the new digest in the root's
   versioned tfvars. Open the pull request from the link in the run summary and merge it:
   until then the nightly drift check reports the root, which is accurate.

The log and summary contain resource addresses and actions only, never plan values: the
repository is public. The saved plan never leaves the runner.

## Identity

This root creates the `infra-deployer` service account and a Workload Identity pool that
accepts only a token minted for this repository's **`deploy.yml` on `main`, started by
`workflow_dispatch`, in the `preprod-deploy` environment** on a GitHub-hosted runner. The
account holds:

- `roles/viewer` and `roles/iam.securityReviewer` to refresh a plan;
- `roles/run.developer`, which updates services and jobs but cannot set their IAM policy;
- `roles/cloudbuild.builds.editor`, and `serviceAccountUser` on `backend-builder` only;
- `serviceAccountUser` on the four runtime identities listed in `preprod.tfvars` only;
- read and write on the state of the four roots above (an IAM condition on the object
  prefix), and object listing on the state bucket;
- `secretAccessor` on `infra-drift-inputs`, the private plan inputs.

It cannot change IAM, secrets, networks, buckets or the other roots' state. The plan guard
is the first barrier and these grants are the second. If the first real run reports a
permission error, add the narrowest role that fixes it, never an owner or editor role.

## Set up once

```sh
terraform -chdir=infra/deploy init -backend-config=preprod.backend.hcl
terraform -chdir=infra/deploy plan -var-file=preprod.tfvars -out=deploy.tfplan
terraform -chdir=infra/deploy apply deploy.tfplan
terraform -chdir=infra/deploy output repository_variables
```

Store the two printed values as GitHub Actions **repository secrets**
(`DEPLOY_WORKLOAD_IDENTITY_PROVIDER`, `DEPLOY_SERVICE_ACCOUNT`). They are identifiers, not
credentials, but the repository is public: secrets keep them out of the settings page and
masked in logs, as the drift check does. The workflow also reuses the variables
`GCP_PROJECT_ID` and `DRIFT_STATE_BUCKET`.

Create the protected environment. With one maintainer the approval is a deliberate pause,
not a separation of duties, so self-review stays allowed:

```sh
REPO=kaligautier/trading-on-IBKR-with-ADK-
gh api -X PUT "repos/$REPO/environments/preprod-deploy" --input - <<JSON
{"reviewers":[{"type":"User","id":$(gh api user --jq .id)}],
 "deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
JSON
gh api -X POST "repos/$REPO/environments/preprod-deploy/deployment-branch-policies" -f name=main -f type=branch
```

## First run

Dispatch with `dry_run` on for each root and read the summary: the build, the state access
and the guard are all exercised, and nothing is applied. Then release one root for real,
merge its recording pull request and check that the drift check stays green.

## Rollback

Dispatch with `digest` set to the previous known-good digest (the previous release pull
request shows it), `dry_run` off. The guard applies unchanged.

## Offline checks

```sh
terraform -chdir=infra/deploy fmt -check
terraform -chdir=infra/deploy init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/deploy validate
terraform -chdir=infra/deploy test
python3 -m unittest discover -s infra/deploy/tests -p 'test_*.py'
```
