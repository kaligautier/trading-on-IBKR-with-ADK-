# Momentum public MCP

Migrated from `kaligautier/deep-copy-finary`, commit
`2f510084f777dea6c047375f22f291ba4a926a24`, directory
`apps/backend/momentum-public-mcp`. FastMCP and fastmcp-slim are pinned to
**4.1.3 (Root Awakening)**; `uv.lock` pins the complete runtime.

This backend exposes six tools, one resource and one prompt over **POST /**. It invokes
the private Momentum consultation API and Market Scanner reader using separate
Cloud Run ID-token audiences. It has no database credentials or execution/admin
permissions. `/health` is a liveness probe, not proof of upstream availability.

## Source organization

Each upstream API owns its client, environment settings and request/response
models under `src/momentum_public_mcp/api`:

```text
api/
  momentum/
    client/
      momentum_client.py # Typed Momentum HTTP calls
      signing.py         # Suggestion caller assertion
    config/
      settings.py       # Momentum URL, IAM flag and signing key
      client_config.py  # Build the authenticated MomentumClient
    dtos/
      request/
        analyses.py     # AnalysisPageRequest: HTTP filters and cursor pagination
        suggestions.py  # SuggestionRequest: POST /suggestions JSON body
      response/
        analyses.py     # AnalysisSummary, AnalysisDetail, ReaderPage
        suggestions.py  # Suggestion response, including moderation status
  market_scanner/
    client/
      market_scanner_client.py # Typed Scanner HTTP calls
    config/
      settings.py       # Scanner URL
      client_config.py  # Build the client with the Scanner token audience
    dtos/
      response/
        market_scan.py  # MarketScan envelope
  auth.py               # Shared Cloud Run identity tokens and headers
  http.py               # HTTP transport and error handling
  config.py             # Shared HTTP defaults and URL validation
  errors.py             # Typed upstream exceptions and diagnostic HTTP status
```

Each `config/client_config.py` builds its API client with the base URL, timeout and
authentication. Client methods accept HTTP request DTOs or path identifiers,
perform one API call, and return a validated response DTO. They do not traverse
pagination or translate the MCP's `limit`/`offset` window.

`application.py` injects the configured clients into `mcp/gateway.py`, the service
layer that translates MCP operations and aggregates reader pages. `domain.py`
owns validated MCP inputs and aggregated results; these are distinct from the
external API's request/response DTOs. `config/config.py`
combines API settings with server settings. Existing environment names are
unchanged; `MOMENTUM_API_USE_IAM` still controls IAM for both API clients, with
a separate token audience for each. `market_scanner` uses an underscore so it
can be imported as a Python package.

MCP capabilities live in separate packages:

```text
mcp/
  gateway.py                   # Connect capabilities to the external clients
  tools/public_tools.py        # Six consultation and suggestion tools
  resources/public_resources.py # Latest published market scan
  prompts/
    public_prompts.py          # Validate prompt arguments and render instructions
    instructions.py            # get_instruction() reads the instruction file
    templates/analyze_ticker.md # Static plain-text instructions
```

The `analyze_ticker` prompt normalizes the ticker and calls
`get_instruction("analyze_ticker")`, then prefixes the normalized ticker.
Python's `importlib.resources` reads the static Markdown file from the installed
package without variable substitution. Retrieving a prompt only returns
instructions: it does not call upstream APIs, invoke an LLM or start an analysis.

Request DTOs are serialized by the clients into query parameters or JSON bodies;
response DTOs validate upstream JSON and filter undeclared response fields.
Optional query filters are omitted when absent, while an empty suggestion reason
remains an explicit JSON string. Caller identity and signatures stay in headers.
Response DTOs use Pydantic's default behavior of ignoring undeclared fields.
The Scanner GET has no request payload, so it has no request DTO package.
The suggestion-specific meaning of HTTP 409 belongs to `MomentumClient`;
conflicts from other endpoints retain the generic sanitized HTTP error.

## Application errors

`errors.py` defines `AppError`, stable `ErrorCode` values and `InstructionError`.
`api/errors.py` defines `MomentumApiError`, `MarketScannerApiError` and
`ServiceIdentityError`. The shared HTTP client raises the exception belonging to
its upstream, including for timeouts and invalid response data. Failure to obtain
Cloud Run identity has its own code, shared by both APIs.

`str(error)` exposes only `[CODE] public message`; `to_dict()` exposes only
`error_code` and `message`. Diagnostic `details` and `upstream_status_code` stay
internal. The latter is the status received from an upstream, not a status to
return to the MCP caller. API response bodies and raw exception messages are not
copied into public errors.

Tools, resources and prompts convert application exceptions into FastMCP's
`ToolError`, `ResourceError` and `PromptError`. FastMCP owns the MCP response;
there is no application mapping to HTTP or JSON-RPC error codes. Unexpected
exceptions remain masked by the server.

## Stateless contract

The HTTP application uses FastMCP's native transport with `stateless_http=True`.
The following contract applies to requests using `2026-07-28`:

- Each request is independent, including `tools/call` as the very first request.
- No `Mcp-Session-Id`, cookies, sticky sessions, shared session store or resumable
  event store. Every request carries its own client capabilities.
- `MCP-Protocol-Version` must match `params._meta["io.modelcontextprotocol/protocolVersion"]`.
- `protocolVersion` and `clientCapabilities` are required under the namespaced
  `_meta`; `clientInfo` is optional. FastMCP handles protocol validation and
  errors without a custom metadata middleware.
- Version negotiation and compatibility with older clients are delegated to
  FastMCP. Legacy initialization is supported by the SDK without creating an
  HTTP session; the application does not impose a single-version allowlist.
- Native `server/discover`, unsupported-version negotiation (`400`/`-32022`),
  and unknown/removed RPC errors (`404`/`-32601`) are tested on HTTP.
- `GET /` and `DELETE /` return 405. No standalone SSE channel is provided.
  This service exposes tools, a resource and a prompt, with no subscriptions, sampling, elicitation,
  roots, background tasks or server log notifications. JSON responses suffice.
- Browser CORS permits public POSTs with the MCP headers, without credentials.

Use `Mcp-Method` (and `Mcp-Name` for a tool call, resource read or prompt retrieval), as required by the current
protocol's HTTP routing rules. The health endpoint alone uses GET.

```sh
curl "$MCP_URL/" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' -H 'Mcp-Name: list_analyses' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_analyses","arguments":{"limit":1},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"curl","version":"1"},"io.modelcontextprotocol/clientCapabilities":{}}}}'
```

Always check `result.isError`, not just HTTP 200.

## Reader migration

The four Momentum tools use `/v1/analyses`, `/v1/analyses/latest`,
`/v1/analyses/{id}` and `/v1/recommendations`. Their public inputs and list output
shape (`structuredContent.result`) are retained. The adapter traverses the
reader's cursors to honor `limit`/`offset`, and fetches all latest pages rather
than silently dropping them. Repeated cursors fail, and the 45-second tool
deadline bounds traversal. Pagination does not create an MCP session.

The resource `momentum://market-scans/latest` returns the current reader envelope
as JSON text in `result.contents` from `resources/read`:
`{id, scan_date, created_at, report}`. `report` preserves the complete v3 data,
including decimal strings, null horizons and arbitration. Consumers of the old
flattened report must read `report.regime`, `report.summary`, `report.assets`.
The removed legacy `session_id` and `recommendation` fields are not fabricated.
The former `latest_market_scan` tool has been removed; consumers must use
`resources/read` with this URI. `resources/list` advertises the resource.

`prompts/list` advertises `analyze_ticker`; retrieve its instructions with
`prompts/get` and `{"name": "analyze_ticker", "arguments": {"ticker": "AAPL"}}`.
The prompt directs the client to consult existing analyses and read the market
resource, then summarize the evidence with dates and identifiers.

## Suggestions through Momentum API

`suggest_ticker` and `get_suggestion_status` call `POST /suggestions` and
`GET /suggestions/{uuid}` on the same `MOMENTUM_API_URL` as the analysis tools,
with the same Cloud Run identity and original HMAC caller assertion. Validation,
quotas, persistence and moderation belong to Momentum API, as in DeepCopy.
The MCP has no storage adapter, database credentials or separate moderation URL.
It cannot approve a suggestion or start an analysis.

The recovered routes are deployed in Momentum API. A live public MCP submission,
status read and duplicate submission returned the same persisted pending record.
The API owns the PostgreSQL transaction, quotas and moderation fields.

## Run and verify

```sh
uv sync --locked --python 3.12
uv run --locked pytest -q
uv run --locked ruff check src tests scripts
uv run --locked ruff format --check src tests scripts
# With Postman CLI >=1.73.0 installed (no login or cloud publication):
uv run --locked python scripts/simulation.py
docker build -t local/momentum-public-mcp:verify .
uv run --locked python scripts/container_smoke.py local/momentum-public-mcp:verify
```

The simulation runs this backend, not a mock of it. Its two local upstream
mocks derive from this repository's Momentum OpenAPI, Scanner producer v3
example/reader envelope, and the recovered DeepCopy suggestions contract. No
external owner's mock was needed: these are local services owned by this project.
The saved collection exercises all six tools, resource discovery/read, prompt
discovery/rendering, a real HTTP write/status cycle
against the Momentum API mock, and a sanitized upstream failure. Unit tests also
cover separate IAM audiences and cursor traversal. Live IAM/data access needs
the deployed checks described in [Terraform](../../../infra/momentum-public-mcp/README.md).

`SUGGESTION_HASH_SECRET` is required for pseudonymization and moderation signing.
Never commit its value. `TRUSTED_PROXIES` is an explicit immediate-proxy CIDR
allowlist; by default forwarded addresses are not trusted. Rate limiting is a
best-effort 60 requests/minute per fingerprint **per replica**, not a distributed
quota. With no trusted proxy configured, callers sharing the direct peer share
that limit. It has no role in protocol session handling.

## Configuration and operational logs

`config/config.py` combines Pydantic `BaseSettings` with a documented `Field` for every
setting. Environment variables override `.env`; invalid ports, proxy CIDRs,
remote cleartext URLs and URLs with credentials fail at startup. The required
signing key uses `SecretStr`, and validation errors hide input values.
`config/constants.py` holds the six tool titles, tags, annotations and shared deadline.

The `observability/` package separates responsibilities:

- `logger.py`: `python-json-logger` JSON formatting and `TraceInjectFilter`.
  Logs contain severity, logger name, module, function, message, `trace_id` and
  `span_id`. IDs are empty outside a trace. `LOG_LEVEL` defaults to `INFO`;
  `NOISY_LOGGERS` keeps HTTPX and HTTPCore at warning level. Standard log messages,
  exception information and explicitly supplied extra fields are serialized;
  callers must not log secrets or private payloads.
- `telemetry.py`: OpenTelemetry SDK and batched Cloud Trace
  export. FastMCP supplies native tool/resource/prompt spans; ASGI and HTTPX add
  incoming request and outgoing API spans. HTTPX propagates child span context.
- `health.py`: `/health` process liveness, with no calls to upstream dependencies.
  Health requests are excluded from tracing.

There is no custom request summary, business counter accumulator or log tail
sampling. The application does not generate an `X-Request-ID` header; correlation
uses OpenTelemetry trace/span IDs. Cloud Run provides its own HTTP request logs.

Set `GOOGLE_CLOUD_PROJECT` to enable Cloud Trace export using Application Default
Credentials. Empty means no network exporter, so local runs need no GCP login.
All instrumented requests are recorded (`ALWAYS_ON`), including when the incoming
parent is unsampled. There is no configurable trace sampling ratio. `/health`
and low-level ASGI send/receive spans remain excluded.

The standard OpenTelemetry exporter sends spans directly, without a custom
attribute or exception filter. Native instrumentation may include URLs, query
parameters and exception details; this is independent of MCP client error masking.
MCP and HTTPX spans identify operation failures, while the ASGI span reflects the
HTTP status (which may be 200 even when a tool fails).
`main.py` initializes OpenTelemetry, configures logging, then creates the
application. The provider shuts down after the HTTP server exits, draining its
export batch.
Cloud Run request-based CPU allocation can delay background batch export while
an instance is idle; billing/CPU allocation is unchanged by this integration.

`tests/test_telemetry.py` uses an in-memory exporter to verify span parentage,
propagation, full trace recording and log correlation without sending data to GCP.
Live Cloud Trace ingestion must be verified after deployment; local tests do not
prove service-account permissions or exported traces in the destination project.

Use the MCP operation span and its HTTPX children to investigate failures and
latency. Application logs emitted inside a span carry its `trace_id` and
`span_id`. Example Logs Explorer filter:

```text
resource.type="cloud_run_revision"
resource.labels.service_name="momentum-public-mcp"
jsonPayload.trace_id="TRACE-ID"
```

The deployment uses the direct Cloud Run URL without a load balancer or Cloud
Armor. The per-instance application limiter remains best effort.

The Docker build pins Python and uv by digest, builds a wheel with a locked
Hatchling toolchain and installs only runtime dependencies in the final non-root
image. It does not run a floating OS upgrade during the build. Dependabot tracks
base images and Python dependencies; FastMCP remains explicitly pinned to 4.1.3.
The container smoke check verifies the entrypoint, protocol, validation errors,
non-root user and absence of development/build tools. The Postman simulation
separately exercises the real HTTP clients against contract-derived upstreams.

## Canonical-event release verified on 2026-10-24

- 71 Python tests, 45 Postman assertions, four Terraform tests and the final
  runtime-container smoke check passed, along with Ruff and pre-commit.
- Cloud Build `d32ec2e2-d8b8-474a-80d7-071d637e8d0d` produced image
  `sha256:dbb35718d90eff4949c6891cbf769e2865f2bc510f9babe5092ec907a4e3a101`.
  The verified wrapper deployed `momentum-public-mcp-00005-gxv` to 100% traffic;
  live business/protocol verification passed and Terraform reported no drift.
- Cloud Logging contained exactly one canonical MCP event for each of two
  read-only probes, with matching trace IDs in Momentum API. A successful list
  included `business.result_count=1`; a missing analysis recorded HTTP 200,
  `outcome=error` and `upstreams.momentum.last_status=404` in the same event.
- The live configuration retains all events (`sample_rate=1`); unit tests prove
  that lower rates still retain errors, cancellations and slow requests.

## Initial operations release verified on 2026-10-24

- 59 Python tests, four deployment-gate tests, 45 Postman assertions and three
  Terraform tests passed. The built container passed its runtime smoke check.
- Cloud Build `87004b53-be13-401c-8274-a1cc96f257bc` produced immutable image
  `sha256:84403edc237778378650405f7673fa0ee0dba6726ba1993f5e6223024ff99da1`.
  Revision `momentum-public-mcp-00004-bcc` received 100% of traffic after the
  verified release wrapper completed. A subsequent Terraform plan was empty.
- Automatic read-only verification retrieved the AAPL analysis and the daily
  scanner report with 25 assets, checked all seven advertised tools, rejected
  legacy handshakes and validated correlation headers on successful/error RPCs.
- Cloud Logging recorded matching trace IDs in MCP and Momentum API for a
  successful list and a missing-analysis lookup. The latter produced an upstream
  404 and `tool_call.outcome=error` despite HTTP 200 at the MCP boundary.
- Both private APIs still returned 403 to unauthenticated requests. No suggestion
  was submitted by this release verification; no load balancer or Armor was added.

## Initial migration verification on 2026-10-24

- 45 Python tests and Ruff checks passed.
- 45 Postman assertions passed over 12 real HTTP requests to the local MCP,
  including an upstream response delayed by 11 seconds.
- Three Terraform tests passed: public ingress/private reader grants, immutable
  image, and numeric secret-version constraints.
- Cloud Run revision `momentum-public-mcp-00003-7sx` received 100% of traffic;
  Terraform reported no drift. Live requests rejected all four 2024/2025 protocol
  versions and the removed `initialize`, `ping` and `logging/setLevel` methods.
- Live consultation returned AAPL analysis `9aee5d94-ce77-4ec9-bf02-5882eda66e02`
  and the 2026-10-24 Scanner report containing 25 assets, with no session headers.
  Both reader endpoints returned 403 without authentication.
- Live suggestion `3683f035-4525-4556-b761-df1e2ae2851c`
  (`MCPTEST-20261024-1230`) was created pending, read from a fresh HTTP request,
  and deduplicated to the same ID. An independent PostgreSQL read confirmed it.
  Its reason explicitly marks it as a verification fixture, not for approval.
- Momentum API revision `momentum-api-00003-g6c` handles suggestions using the
  existing one-connection pool. Its 261 tests passed with 95% branch-inclusive
  coverage; 33 Postman assertions exercised the real MCP/API/PostgreSQL chain,
  and 56 assertions passed against the exact release container image.
- These deployment checks preceded PR preparation; GitHub CI results are tracked
  separately on the dependent pull requests.
