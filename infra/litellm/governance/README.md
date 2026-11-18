# Agent governance

This Terraform root manages LiteLLM teams, keys and per-agent budgets directly.
Infrastructure and private-network setup remain in `infra/litellm`; no Python
provisioning script or Cloud Run key-provisioning job is involved.

Requirements: Terraform 1.11+, the deployed gateway, PostgreSQL, and a runner
connected to the private VPC. Use the separate governance service account reported
by `terraform -chdir=infra/litellm output agent_governance` (for example through
`GOOGLE_IMPERSONATE_SERVICE_ACCOUNT`). The caller needs permission to impersonate
it, and the chosen backend identity needs access to its GCS state prefix.
The identity can read the admin key and client secrets and create client versions;
application identities can still read only their own secret.

Apply the infrastructure root first to create `litellm-governance` and its scoped
secret grants, then refresh `output agent_governance` and update the runner's
impersonation target. This identity exists without `client_tools_image`; the
optional `litellm-key-bootstrap` job retains its separate, narrower permissions.
Backend access and caller impersonation grants remain operator prerequisites;
this change does not grant project-wide secret access or state-bucket access.

## Configure and apply

Add the application SA to `client_service_accounts` in the infrastructure root and
apply it to create its secret container and IAM. Then copy `config.example.tfvars`
to an ignored `governance.local.tfvars` and fill the non-secret values. Use a
separate GCS state prefix from the infrastructure root:

```sh
terraform -chdir=infra/litellm/governance init \
  -backend-config='bucket=YOUR_STATE_BUCKET' \
  -backend-config='prefix=litellm/governance'
terraform -chdir=infra/litellm/governance plan -var-file=governance.local.tfvars
terraform -chdir=infra/litellm/governance apply -var-file=governance.local.tfvars
```

The example gives Scanner $3/1d and another agent $4/7d. These are USD accounting
budgets; the optional global proxy budget also applies. The pinned proxy computes
reset boundaries in UTC. Accounting is asynchronous and concurrent requests can
overshoot the cap. A seven-day interval does not imply a Monday-to-Sunday week.
For later quota changes, edit the agent's budget/window and apply this root.

The official provider is pinned to 1.106.0. Admin credentials are read with Google's
ephemeral secret resource. New keys are generated with ephemeral random passwords
and stored with `secret_data_wo` before registration. The key provider's write-only
`key` receives the ephemeral secret; state contains only its SHA-256 identifier.
Do not enable Terraform/provider debug logs while handling real credentials.

## Rotate agent keys before the 30-day expiry

Agent keys expire after 30 days (`duration = "30d"`, ignored on adopted keys) and
nothing rotates them. An expired key returns `401 Authentication Error - Expired
Key` from the gateway: the Scanner daily job failed from 2026-11-05 until the keys
were rotated on 2026-11-17. Rotate every key before its expiry (check the
`Expired`/`Expires` column of the admin UI Virtual Keys page).

The agent key is a write-only attribute, so Terraform cannot see a changed key:
omitting `secret_version`/`existing_token_id` only creates unregistered secret
versions. Replace the key resources explicitly, in one run:

```sh
terraform plan -out=policy.tfplan \
  '-replace=module.policy.litellm_key.agent["AGENT"]'   # one flag per agent
```

Check the plan: one new secret version and one replaced `litellm_key` per agent,
nothing else. Then apply it and, in the same change, point each consumer's secret
version (`litellm_gateway.key_version` for the Scanner, `llm_key_version` for
Momentum) at the new version.

Known pitfalls, all seen on 2026-11-17:

- The destroy of the old key happens before the new one is registered. A failure
  in between leaves the agent without any valid key until the apply is completed.
- The governance service account lacks `secretmanager.versions.enable`. The
  provider then fails right after creating the version, the new key is never
  registered and the old one is already destroyed. Grant that permission to the
  governance service account before rotating, or recover by registering the
  existing version: set `secret_version` to it and `existing_token_id` to
  `sha256` of its value, drop the key `import` block, run `terraform state rm` on
  the errored `google_secret_manager_secret_version.agent[...]` entries so the
  version is not destroyed, then plan and apply.
- A deployed job that still carries the previous `secret_version`/`existing_token_id`
  would replace the new key with the old one on its next `apply`. Update its
  inputs after every rotation.
- Release variables are not versioned: before planning a consumer root, compare
  every secret version in its local file with the deployed service (a stale file
  rolled the Scanner API and Momentum database secrets back from version 2 to 1).

An automated rotation, or a longer `duration` for agent keys, would remove this
recurring outage; it needs a decision on key lifetime.

### Expiry alert

When `key_expiry_alert` is set in the `infra/litellm` root, Secret Manager publishes
a rotation reminder for every agent-key secret `lead_days` (default 5) before the
30-day expiry, and Cloud Monitoring e-mails the configured address. A second alert
fires on any `Expired Key` error in Cloud Run logs. Nothing is rotated
automatically. After each rotation, set `key_expiry_alert.rotated_at` to the
creation time of the new secret versions and apply the root, or the next reminder
keeps the old schedule.

## Adopt existing keys

For an existing team, set `team_id` to its actual ID and `import_team = true`.
For each existing key, configure BOTH `secret_version` (numeric, never `latest`)
and `existing_token_id` (its SHA-256 management ID from `/key/info` or the admin UI).
Import blocks adopt them in place. Inspect the plan: it must not replace a key or
create another team. The selected secret must match the configured token ID; a
postcondition also refuses to manage a different key already tracked in state.
No raw client key is needed in tfvars or import commands.

The existing alias, expiry and accumulated spend are retained. New keys get a
30-day expiry. A no-op plan makes no writes and leaves the reset timestamp alone.
Provider 1.106.0 resends `budget_duration` on key updates, so a policy change can
recompute the next reset even when the duration string is unchanged. It does not
clear accumulated spend. Review policy changes near a reset boundary accordingly.

Import a team without a shared budget (`max_budget: null`, never zero). The
provider cannot reliably clear a pre-existing cap with an omitted value. A
`litellm_team` data source preserves the API's null/zero distinction and blocks
key reconciliation whenever the team has any shared cap, including zero.

## Verification and lifecycle

Copy the `client_key_versions` output to the infrastructure root to pin agent
runtime/verification jobs. Run `litellm-verify-CLIENT_NAME` with the agent SA to
verify private inference after applying. Local tests use simulated provider
responses and do not establish cloud connectivity or production spend accounting.

For rotation, create and verify a replacement identity/key before switching the
application, then revoke the old key. Never change a selected secret version and
expect a write-only attribute to retarget the key already in state. Import its
replacement explicitly. Team deletion and new secret-version deletion are
protected; removal/rotation requires an explicit reviewed lifecycle change so
credentials are not silently lost.

Sources: [LiteLLM provider](https://registry.terraform.io/providers/BerriAI/litellm/1.106.0/docs),
[Google ephemeral secrets](https://registry.terraform.io/providers/hashicorp/google/7.46.1/docs/ephemeral-resources/secret_manager_secret_version),
[Terraform write-only values](https://developer.hashicorp.com/terraform/language/manage-sensitive-data).
