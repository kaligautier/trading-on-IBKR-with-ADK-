# Rebuild LiteLLM

Terraform can reconstruct the services, networking, IAM and secret references.
It cannot reconstruct credential values, PostgreSQL rows or a console-created
OAuth client from public source code. Keep these independent recovery assets.

| Asset | Authoritative storage | Needed to recover |
| --- | --- | --- |
| Infrastructure code and image digests | Git | The released commit |
| Terraform state | Private versioned GCS bucket | A known good object generation |
| Deployment targets and version numbers | Protected local config / deployment records | Backend and project files plus pinned secret versions |
| Passwords, master key, encryption salt, virtual keys, CA | Secret Manager | Enabled versions and access policies |
| Models, users, encrypted provider credentials, virtual-key hashes, usage | Dedicated PostgreSQL database | Database backup and stable encryption salt |
| IAP OAuth client | Google Auth Platform / protected client export | Client ID/secret, redirect URI, audience and test/published status |

Credential containers have Terraform `prevent_destroy`; version destruction is
delayed for 30 days. Cloud Run services have deletion protection. Config versions
use `ABANDON` to preserve rollback targets. These guards do not prevent a project
owner from deleting resources outside Terraform. Delayed version destruction
does not protect deletion of an entire secret container. Do not treat these
controls as an independent backup.

## Lost checkout

Restore the released Git commit and the ignored deployment configuration from
protected storage. Authenticate with the authorized deployment account, verify
the effective identity and target project, then initialize the original backend:

```sh
terraform -chdir=infra/litellm init -backend-config=config/preprod.backend.local.hcl
terraform -chdir=infra/litellm plan -var-file=config/preprod.local.tfvars \
  -var-file=config/release.local.tfvars -out=recovery.tfplan
```

Include the provider file when configured. A healthy unchanged deployment must
plan no changes. Review every action before applying. Never apply an old plan
from a different checkout or regenerate the encryption salt automatically.

## Lost or damaged Terraform state

Stop all applies. Inspect GCS object generations for the original state prefix.
Restore a known good state generation using the bucket's version/soft-delete
recovery features. Validate state lineage, serial and resource IDs against the
live project before applying. Do not upload state into a public bucket or Git.

If no usable state remains, import existing resources into the same module using
the provider's resource-specific import IDs. Begin with the secret containers,
service accounts, network, artifact repository and deployed services. Reconcile
the plan until it shows only intended changes. An empty state is not proof that
the live infrastructure is empty.

## Deleted workloads, intact database and secrets

Keep `stage = "service"`. Plan with all local configuration files, confirm that
only missing workloads/network/IAM are recreated, then apply the reviewed plan.
Do not go back to the foundation stage while other services remain deployed;
that would propose deleting them.

## Full infrastructure loss

1. Restore the original secret values and database backup, including the stable
   encryption salt. Recover/import surviving secret containers first.
2. Apply `stage=foundation` only when workloads truly no longer exist.
3. Restore enabled numeric credential versions and pin them in the release file.
4. Apply `stage=migrations`, execute the migration job, and require success.
5. Apply `stage=service` and restore the project-level OAuth configuration from
   the protected export if it was lost. Never bypass IAP to fix login.
6. Restore client virtual keys consistently with their database hashes; provision
   replacements explicitly if the original plaintext keys cannot be recovered.

Existing-secret bootstrap reruns preserve enabled versions. They do not recover
an old salt that was destroyed. Losing the salt with encrypted provider
credentials requires provider credential re-onboarding after database recovery.

## PostgreSQL restore

Use the database provider's backup/restore or a protected verified PostgreSQL
dump. Restore the dedicated LiteLLM database into a separate target first and
verify schema, users, model configuration and migration status. Keep database
passwords, backups and dumps outside public source control. The five Secret
Manager credentials are not a backup of database rows.

Restore the original salt alongside the database. Run upstream migrations before
the service upgrade; database downgrade compatibility must be checked against
the upstream migration history. Do not assume that rolling back a container
reverts the database schema.

## Acceptance after recovery

- Admin service has IAP enabled and an explicit user allowlist; anonymous
  internet requests are redirected or denied, even with a LiteLLM key.
- Authorized browser passes IAP, then signs in with the separate LiteLLM password.
- Gateway ingress is internal-only and has IAP disabled; internet access is denied.
- A VPC-attached client with its inference key reaches Vertex, and its key cannot
  create keys or select an unapproved model. It sends no IAP identity token.
- Usage is persisted in PostgreSQL without prompt/response spend-log payloads.
- Keys survive a service revision, and a fresh Terraform plan shows no changes.

Record the released commit, revisions, secret-version numbers and validation
results in protected deployment records. Do not record credential values there.

Reference: [Secret Manager delayed destruction](https://docs.cloud.google.com/secret-manager/docs/delay-destruction-of-secret-versions).
