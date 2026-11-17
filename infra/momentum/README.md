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
The secret containers have Terraform deletion protection. Retiring them requires
an explicit reviewed change to disable that protection and an apply before deletion.
Individual version destruction is delayed by 30 days; this does not delay deletion
of the whole secret container. Use a root HTTPS URL for `gateway_url`.

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


## Verified preprod execution

On 2026-10-21, execution `momentum-analysis-stwdd` completed with exit code 0
in 7m19s. The worker image in `config/preprod.release.tfvars` contains application
commit `4e989df`. Terraform reports no drift after deployment.

AAPL analysis dated 2026-10-20 used all four analysts, one investment/risk debate
round, and the existing LiteLLM gateway: 26 model calls, 20 tool calls,
207,895 input tokens and 19,833 output tokens. An independent PostgreSQL read
verified result `da01c45b-ca82-4848-acdf-7fc92b508cbd` and all eleven child-table
categories (including five debate arguments). Its session
`9985e7ae-a9d4-42ff-8ce1-33a34f880880` has 92 events, all correlated with
invocation `e-89a082be-e320-4973-93cb-6700ea910107`.

This proves real inference, successful worker completion and committed structured
results/session history. It does not establish financial accuracy or complete
provider coverage. Earlier failed runs remain in session history and have no
partial result rows. Momentum CI passes; the separately triggered Scanner audit
still reports inherited aiohttp/certifi dependency findings.

## Verified PostgreSQL transport

Before deploying this worker, publish session/result URL secret versions using
`sslmode=verify-full`. Older `sslmode=require` URLs are intentionally rejected.
The worker mounts the existing `database_ca_secret_id` at `/etc/database/ca.pem`
using pinned `database_ca_version`; both pools consume `DATABASE_CA_FILE`. Any
`sslrootcert` in a URL must match that mount. Never put credential values in state.
Verify both session and result connections with the deployed CA/URL versions
before claiming rollout success. Local loopback fixtures may disable TLS.
