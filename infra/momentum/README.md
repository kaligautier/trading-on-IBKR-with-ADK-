# Momentum private Cloud Run Job

Independent Terraform state: `preprod/momentum`. The worker uses the existing
private-services network and cloud-run-egress subnet to reach LiteLLM. It has
access only to its two PostgreSQL runtime secrets and its existing LiteLLM key;
there is no direct Vertex AI grant, migration credential or public HTTP service.

```sh
terraform init -backend-config=config/preprod.backend.hcl
terraform plan -var-file=config/preprod.tfvars -out=foundation.tfplan
terraform apply foundation.tfplan
```

Upload the two runtime URLs as Secret Manager versions using a protected local
file or stdin; never pass secret values to Terraform. Both URLs must target
`momentum`, with separate `_sessions` and `_analysis` runtime logins.
Build `apps/backend/momentum-adk/Dockerfile` for linux/amd64 and push to the
`momentum/worker` Artifact Registry repository. Set `image` to its immutable
sha256 digest in a release variable file. The verified preprod image is recorded
in `config/preprod.release.tfvars`. Then plan/apply again
with both variable files. This creates the job without executing a paid analysis.

Execute one authorized request through `gcloud run jobs execute momentum-analysis`
with a `TA_ANALYSIS_REQUEST` environment override containing a validated
AnalysisRequest JSON (ticker, analysis_date, requested_by and session_id required).
Use `max_debate_rounds=1` and `max_risk_discuss_rounds=1` for the first verification.
Cloud Run enforces one task per execution, parallelism one, no retries and a
30-minute timeout. Each database pool uses one connection with no overflow;
concurrent executions remain subject to the database role connection limits.

Verify both Cloud Run success and the durable result linked by session_id and
invocation_id. A started execution or an ADK session alone is not completion.
Decision-memory/cache files are ephemeral in `/tmp`; session/event history and
financial results persist in PostgreSQL. This rollout does not include the HTTP
dispatcher or a cross-execution durable filesystem memory store.

Validation: `terraform validate`, `terraform test`. Provider checksums include
both macOS ARM64 and Linux AMD64. Direct VPC design follows the [Cloud Run
networking documentation](https://docs.cloud.google.com/run/docs/configuring/vpc-direct-vpc).
