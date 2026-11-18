# Nightly drift detection

Proves every night that `origin/main` describes production. The workflow
[`infra-drift.yml`](../../.github/workflows/infra-drift.yml) plans each Terraform
root read-only (`plan -lock=false -detailed-exitcode`). A non-empty plan or a plan error
fails the job and opens or updates an `infra-drift` issue for that root.

The repository is public, so the job never prints plan output. The log and the issue
contain only resource addresses and actions.

## Identity

This root creates a read-only identity, reachable only by the reviewed workflow on
`main` of this repository through Workload Identity Federation:

- `roles/viewer` and `roles/iam.securityReviewer` on the project, to refresh a plan;
- `roles/storage.objectViewer` on the state bucket (state is read, never written);
- `secretAccessor` on `infra-drift-inputs` only.

If the first run reports a permission error on a refreshed resource, add the narrowest
read role that fixes it; never a write role.

## Private plan inputs

Invoker and IAP identities, SSO settings, key fingerprints and the alert address stay out
of Git. They live in one Secret Manager secret, a JSON map `{root: {file: content}}`.
Upload it from the machine that holds the ignored `*.local.tfvars` files, without
printing it:

```sh
python3 infra/drift/scripts/build_inputs.py | \
  gcloud secrets versions add infra-drift-inputs --data-file=- --project=preprod-deep-copy
```

The nightly job reads the latest version: this is the one secret not pinned to a number,
because it must follow the plan inputs. Re-run the command whenever an input file changes.

## Apply once

```sh
terraform -chdir=infra/drift init -backend-config=preprod.backend.hcl
terraform -chdir=infra/drift plan -var-file=preprod.tfvars -out=drift.tfplan
terraform -chdir=infra/drift apply drift.tfplan
terraform -chdir=infra/drift output repository_variables
```

Set the printed values as GitHub Actions **repository variables** (they are identifiers,
not secrets): `GCP_PROJECT_ID`, `DRIFT_WORKLOAD_IDENTITY_PROVIDER`, `DRIFT_SERVICE_ACCOUNT`
and `DRIFT_STATE_BUCKET`. Then run the workflow once with **Run workflow** and check that
every root reports `No changes`.

## Scope

Every root with state is in the workflow matrix, including `budget-guard` (its ignored `budget.local.tfvars` is part of the private inputs). `litellm/governance` is excluded: its provider reads the gateway master key. It is planned
by the `litellm-agent-governance` Cloud Run job. The matrix must list every root that has
state; add a root here in the same change that creates it.
