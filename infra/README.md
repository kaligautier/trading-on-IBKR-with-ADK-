# Infrastructure

Each stack has an independent Terraform root. The policy module is tested
separately. Run commands from the repository root and pass the appropriate
`-chdir` path.

| Root or module | Ownership and guide |
| --- | --- |
| `bootstrap/` | APIs, protected state bucket, Artifact Registry and database secret metadata; see [Scanner setup](market-scanner/README.md#deploying-to-your-project). |
| `market-scanner/` | Private Scanner service, scan job, scheduler and IAM; [deployment guide](market-scanner/README.md). |
| `reader/` | Private consultation API and read-only database access; [deployment guide](reader/README.md). |
| `momentum/` | Private Momentum analysis runtime; [deployment guide](momentum/README.md). |
| `litellm/` | Inference gateway and IAP-protected administration; [deployment guide](litellm/README.md). |
| `litellm/governance/` | Teams, keys and per-agent budgets; [guide](litellm/governance/README.md). |
| `litellm/governance/policy/` | Team/key policy module used by the governance root; [guide](litellm/governance/README.md). |
| `frontend/build/` | Frontend builder and source storage; [build guide](frontend/README.md). |
| `momentum-public-mcp/` | Public stateless MCP and private reader invocation; [deployment guide](momentum-public-mcp/README.md). |
| `frontend/` | Public frontend and reader invocation rights; [deployment guide](frontend/README.md). |

The database is external to Terraform; see [database setup](../database/README.md).
Secret values are supplied separately and never enter Terraform state.

## Validation

Use Terraform 1.9 or later, below 2.0. In a clean checkout:

```sh
(
set -e
terraform fmt -check -recursive infra
for root in infra/bootstrap infra/market-scanner infra/litellm infra/reader infra/momentum infra/frontend/build infra/frontend; do
  terraform -chdir="$root" init -backend=false -input=false -lockfile=readonly
  terraform -chdir="$root" validate
  terraform -chdir="$root" test
done
)
```

Tests use mock providers and do not prove GCP access or persistence. Use a separate
checkout if a root is already initialized against a live backend. Governance has
additional validation commands in the [LiteLLM workflow](../.github/workflows/litellm.yml).

## Public repository hygiene

Commit provider lock files and placeholder examples. Keep state, saved plans,
`.terraform/`, override files, automatic variable files and local deployment
inputs out of Git. Use `*.local.tfvars` (or `*.local.tfvars.json`) for private
inputs, and name saved plans `*.tfplan` or `*.plan`. Ignore rules are a safety
net; inspect `git diff --cached` before publishing.

Credential values are uploaded directly to Secret Manager outside Terraform.
Terraform manages their metadata, numeric version references and scoped access
grants. Marking a Terraform variable `sensitive` only redacts display; it does
not remove the value from state or a saved plan. Use ADC locally and short-lived
identity federation in CI; keep backend credentials out of HCL and
`-backend-config` files. Restrict state-bucket IAM to infrastructure operators.
The bucket enforces private access and retains versions for recovery.

See HashiCorp's [sensitive data guidance](https://developer.hashicorp.com/terraform/language/manage-sensitive-data)
and [GCS backend authentication guidance](https://developer.hashicorp.com/terraform/language/backend/gcs).

CI initializes with the committed lock files and no backend, then validates and
runs mock-provider tests for roots with test suites. These jobs require no cloud
credentials and do not apply infrastructure. Bootstrap and scanner checks live
in `scanner.yml`; reader, Momentum, LiteLLM and frontend checks live in their respective
workflows.
