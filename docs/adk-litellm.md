# ADK agents through LiteLLM

The researcher, critic and synthesizer send native Gemini requests to the
private LiteLLM gateway. LiteLLM selects its configured Vertex/Gemini upstream
and accounts for usage against the application's virtual key. Agents never
call Vertex directly or switch provider when the gateway fails.

This uses ADK's `Gemini` transport with a custom GenAI client, rather than the
OpenAI-format `LiteLlm` connector. The gateway already permits LiteLLM's
[`/v1beta/models/...:generateContent` API](https://docs.litellm.ai/docs/generateContent).
Native transport retains Google Search, function calls, thinking configuration,
structured outputs and streaming. No additional LiteLLM Python dependency is
needed in the scanner image.

## Application configuration

Copy the scanner's `.env.example` to its ignored `.env` and set:

```dotenv
LITELLM_API_BASE=https://YOUR_GATEWAY.run.app
LITELLM_API_KEY=YOUR_APPLICATION_VIRTUAL_KEY
MODEL=YOUR_CONFIGURED_GEMINI_ALIAS
GOOGLE_CLOUD_PROJECT=YOUR_RUNTIME_PROJECT
```

Use the gateway root URL with no `/v1`, `/v1beta` or `/gemini` suffix. `MODEL`
(or `MARKET_SCANNER_MODEL`) must match an alias authorized for the virtual key.
Only native Gemini-compatible models are supported by this transport.
The application sends `Authorization: Bearer <virtual-key>` without IAP or a
Google identity token. Legacy shared Vertex environment variables do not select
the inference backend; the client explicitly disables both SDK Vertex flags.

Missing or invalid gateway settings fail at startup. The private Cloud Run URL
requires access from its VPC; a normal local process cannot reach it. Use a
locally reachable gateway for development, or run the scanner in the configured
VPC. Keep the real key in an ignored environment file or Secret Manager.
Project configuration remains required for the scheduled job dispatcher;
inference does not require application ADC.
HTTPS is required except for numeric loopback addresses used by local tests.
The async client uses HTTPX with redirects disabled so requests stay on the
configured gateway. Configuration errors hide raw input values.

## Errors

SDK API, transport and response validation failures become `LiteLLMError` with code `LITELLM_ERROR` (3004), HTTP 502 and message
`LiteLLM gateway request failed`. Safe diagnostic details contain the exception
type and, for HTTP errors, the upstream status. Raw upstream messages and
credentials are excluded from the custom exception and its displayed traceback.

`POST /run` returns `{"error":"LiteLLM gateway request failed"}` with HTTP 502.
Once an SSE response has started, `/run_sse` keeps HTTP 200 and emits ADK's error
event containing `LiteLLMError`. Callers must check events for errors; a transport
200 does not prove a successful scan. The scheduled worker exits with status 1
and logs the custom error code. A failed scan stops before report persistence.

## Cloud Run configuration

Provision and verify the gateway and scanner virtual key using
[`infra/litellm`](../infra/litellm/README.md). That stack grants the scanner
service account access to its own key secret. Supply the runtime Terraform
root with the gateway URL, network, subnet and pinned numeric key version:

```hcl
litellm_gateway = {
  url         = "https://YOUR_GATEWAY.run.app"
  key_secret  = "litellm-client-scanner"
  key_version = "1"
  network     = "private-services"
  subnetwork  = "cloud-run-egress"
}
```

Both the API service and daily worker mount that secret and attach to the same
VPC as the gateway. The scanner no longer receives `roles/aiplatform.user` from
the runtime Terraform root. Review the plan before applying: this branch needs
the matching application image and gateway configuration together.

## Image publication

`Scanner checks` builds the `linux/amd64` application image on pull requests and
relevant pushes to `main`. An offline container test verifies startup, non-root
execution, graph imports, required gateway configuration and worker failure
without a database. It does not prove live inference or database persistence.

To publish images, first apply the bootstrap stack in your own project, then:

1. Configure [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
   for GitHub and a dedicated publisher service account. Restrict the provider
   condition to your numeric repository and owner IDs, `refs/heads/main`, and
   the `scanner.yml` workflow. Restrict impersonation to the `scanner-release`
   environment subject; grant `roles/iam.workloadIdentityUser` on this account
   only. Grant it `roles/artifactregistry.writer` on the `market-scanner`
   repository only. It needs no Cloud Run, Terraform state or secret access.
2. Create the GitHub environment `scanner-release`, restrict it to `main`, and
   configure required reviewers according to your release policy. Protect
   `main` with review and required Scanner/LiteLLM checks before merging.
3. Set environment variables `GCP_PROJECT_ID`, `GCP_REGION`,
   `GCP_WORKLOAD_IDENTITY_PROVIDER` (full provider resource name), and
   `GCP_ARTIFACT_PUBLISHER` (service account email). Set the **repository**
   Actions variable `SCANNER_PUBLISH_ENABLED=true` last.

Publication runs only on `main`, after all Scanner checks pass. It can also be
triggered with `workflow_dispatch` on `main`. Forks are disabled by default and
must configure their own identity and registry. The release job builds and
tests its image before requesting a short-lived token, then publishes that same
image with the commit SHA tag. No service-account JSON key is used.

The job summary records the immutable image reference for Terraform's `image`
variable. Review the Terraform plan with the matching gateway configuration
before deployment. Retain the previous image digest and configuration for
rollback. Publication does not apply Terraform, migrate a database, or establish
that a scan completed. GCP federation and GitHub protections are prerequisites
configured outside this workflow; they are not created automatically.

## Validation

From `apps/backend/market-scanner-adk`:

```sh
TZ=UTC uv run pytest -q src/test/unit
uv run ruff check src
```

The gateway tests exercise the real ADK graph and GenAI serializer, stubbing
only gateway HTTP responses. They cover all three agents, structured schemas,
Google Search declarations, a function-call round trip, custom HTTP/SSE errors,
absence of direct-provider fallback and no persistence on failure. They do not
prove live LiteLLM accounting or upstream inference. Run the existing native
gateway smoke tests and an authorized live scan after deployment for that proof.
