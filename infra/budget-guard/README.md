# Budget kill switch

Independent Terraform root that disables costly APIs once a project's monthly
spend reaches its budget, as a backstop against a leaked credential.

Flow: Cloud Billing budget → Pub/Sub → private Cloud Function → Service Usage
`:disable`. By default it only disables `aiplatform.googleapis.com` (Vertex AI) in
the target project; Cloud Run, the database and state are untouched. The function
runs as a dedicated service account whose custom role can only disable services.

**Limits to know**

- Billing data lags by hours (up to a day). This bounds a leak, it does not stop
  it instantly. Pair it with Vertex AI quotas and restricted credentials.
- Re-enable the API with `gcloud services enable aiplatform.googleapis.com
  --project PROJECT` once the cause is fixed. It is not re-enabled automatically.
- Credits are excluded from the budget (`EXCLUDE_ALL_CREDITS`) so free credit does
  not hide real consumption.
- Not applied or exercised against a live project by the PR checks.

Create ignored `budget.local.tfvars` with `project_id`, `billing_account_id` and,
if needed, `budget_amount`, `currency_code`, `services_to_disable`. Then:

```sh
terraform init -backend-config='bucket=YOUR_STATE_BUCKET' \
  -backend-config='prefix=budget-guard'
terraform plan -var-file=budget.local.tfvars -out=budget.tfplan
terraform apply budget.tfplan
```

The applier needs `roles/billing.costsManager` (or admin) on the billing account,
and project owner-level rights to create the function and IAM. If you already
created console budgets for the same project, delete them or they will duplicate
the alerts.

Verify after applying: publish a test message on the topic with
`{"costAmount": 31, "budgetAmount": 30, "budgetDisplayName": "test"}` on a
throwaway project (it really disables the API), and confirm below-budget messages
(`costAmount` 5) only log.

Offline checks: `terraform init -backend=false && terraform validate && terraform test`.
