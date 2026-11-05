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

The Python package is `app` under `src/app`. The `momentum-public-mcp` command
loads `app.main:main`; `python -m app.main` uses the same entrypoint. `mcp`
remains the external MCP SDK package. Run each backend with its own environment.

Each upstream API owns its client, environment settings and request/response
models under `src/app/api`:

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
        suggestions.py  # SuggestionRequest: POST /v1/suggestions JSON body
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
perform one API call, and return a validated response DTO. They preserve the page envelope and opaque cursor without following it.

`application.py` injects the configured clients into `core_components/gateway.py`, the service
layer that translates MCP operations and forwards one reader page per tool call. `domain.py`
owns validated MCP inputs; these are distinct from the
external API's request/response DTOs. `config/config.py`
combines API settings with server settings. Existing environment names are
unchanged; `MOMENTUM_API_USE_IAM` still controls IAM for both API clients, with
a separate token audience for each. `market_scanner` uses an underscore so it
can be imported as a Python package.

MCP capabilities live in separate packages:

```text
core_components/
  gateway.py                   # Connect capabilities to the external clients
  tools/public_tools.py        # Six consultation and suggestion tools
  resources/public_resources.py # Latest published market scan
  prompts/
    public_prompts.py          # Validate prompt arguments and render instructions
    instructions.py            # get_instruction() reads the instruction file
    templates/analyze_ticker.md # Static plain-text instructions
```

The `momentum_analyze_ticker` prompt normalizes the ticker and calls
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

## Component namespaces

Two native `LocalProvider` instances group components by upstream API.
Each uses FastMCP's [Namespace transform](https://gofastmcp.com/servers/transforms/namespace):

- `momentum`: the six tools, for example `momentum_list_analyses`, and the
  `momentum_analyze_ticker` prompt.
- `market_scanner`: the resource at
  `momentum://market_scanner/market-scans/latest`.

There is one HTTP server and one middleware chain. The namespace changes public
component names and resource URIs, while tool versions, input/output schemas and
opaque API cursors retain their contracts. Scanner currently exposes a resource,
not a tool. Refresh `tools/list`, `resources/list` and `prompts/list` after this
migration. Old unprefixed names and the old resource URI are no longer callable.
Prompt instructions and the local Postman collection use the public names.

## Middleware

`src/app/middleware/middleware.py` registers middleware in incoming-request order:

1. `RequestLoggingMiddleware`, a thin subclass of native `LoggingMiddleware`,
   records method, source, outcome and duration for requests and notifications.
   Payload logging is disabled. Its error formatter records only the exception
   class because native FastMCP 4.1.3 includes exception text even when payload
   logging is disabled. This changes logging only: errors are re-raised unchanged.
   Its `on_call_tool` hook logs the public tool name, argument count and an
   `arguments` JSON field before execution. Argument values are included; keys
   containing token, secret, password, authorization, API key or cookie markers
   are masked recursively, including `page_token`. This is name-based masking,
   not content inspection of free-text fields. Original arguments are forwarded
   unchanged, and the hook returns the original result.
2. Native `SlidingWindowRateLimitingMiddleware` enforces the existing 60 requests
   per minute per caller fingerprint per replica. The outer logger observes
   rejected requests too. `/health` stays outside MCP middleware.

FastMCP can perform an additional discovery operation when resolving HTTP routing
metadata; that operation has its own log pair. Other framework logs and native
OpenTelemetry spans retain their existing behavior. No payload-redaction claim
is made for those independent sources.

Duration is already provided by native logging. Cache, retries, response
truncation and ping are not enabled: pages remain fresh, suggestions retain a
single execution, structured output schemas remain available and HTTP is stateless.

## Standalone Skill example

`examples/sill.py` defines the supplied `release-notes` skill and its
`template.md`, served by `SkillCatalogProvider`:

```sh
uv run --script examples/sill.py
```

The script's inline dependency pins FastMCP **4.2.0a2**, which includes this
experimental API. It runs separately from this service's pinned 4.1.3 environment
and is not registered on the public server. A client can discover/read
`skill://release-notes/SKILL.md`, `skill://release-notes/template.md` and the
manifest. See the [FastMCP 4.2 release](https://github.com/PrefectHQ/fastmcp/releases/tag/v4.2.0a2).

## Application errors

`errors.py` defines `InputError`, `AppError`, stable `ErrorCode` values and
`InstructionError`. Domain input checks raise `InputError` with public messages;
the tool boundary converts only these known input failures and `AppError` to
`ToolError`. An unexpected `ValueError`, `TypeError` or other internal exception
is left to FastMCP's `mask_error_details=True`, never exposed with `str(error)`.
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

## FastMCP tool contracts

Following [FastMCP's tool guidance](https://gofastmcp.com/servers/tools), every tool
has a title, public tags, parameter descriptions, a typed output schema and an
explicit 45-second timeout. `Annotated` and `Field` preserve pagination bounds in
`inputSchema`; the page-size validator changes only the public error message.
There is no custom success/error envelope: expected failures use `ToolError`,
and FastMCP produces `result.isError=true` with text content (HTTP 200).

Each method in `core_components/tools/public_tools.py` declares its explicit
`name`, `title`, LLM-facing `description`, domain `tags` and `meta` directly on
the standalone `@tool` decorator. Bound methods are registered by the provider;
the namespace adds `momentum_` once. Function docstrings retain per-parameter
documentation. Shared annotations, deadlines and analysis route versions remain
in `config/constants.py`.

Discovery exposes `meta` as `_meta.upstream`, with the API name, HTTP method
and relative endpoint path. It contains no private base URL or credentials.
For example, `momentum_list_analyses` advertises
`{"api": "momentum", "method": "GET", "path": "/v1/analyses"}`. Native tool
selection still uses `_meta.fastmcp.version`; a custom `meta.version` would only
be descriptive metadata. No second version source is declared. Tests compare
the advertised upstream operation with Momentum's OpenAPI contract.

| Tools | `readOnlyHint` | `destructiveHint` | `idempotentHint` | `openWorldHint` |
| --- | --- | --- | --- | --- |
| Five consultation tools | `true` | `false` | `true` | `true` |
| `momentum_suggest_ticker` | `false` | `false` | `true` | `true` |

Suggestions are idempotent because Momentum's suggestion repository returns the
existing record for a symbol without updating it, including concurrent submissions.
It never starts an analysis. All tools call an external API, hence `openWorldHint`.
These annotations describe behavior; authorization, the public allowlist and rate
limits remain independent enforcement mechanisms.

### Tool versions follow upstream routes

All six Momentum tools declare FastMCP `version="1"`, matching the `/v1/...`
routes they call. `api/momentum/config/constants.py` provides their version and
HTTP prefix from the same value. Tests check that these routes exist in the
Momentum OpenAPI contract and that tool discovery advertises that version.
This includes the suggestion intake and status tools, backed by `/v1/suggestions`
and `/v1/suggestions/{suggestion_id}`.

The MCP server's `0.1.0` and the OpenAPI document's `info.version` are independent
metadata; neither selects an upstream HTTP route. Do not use one global version
for tools backed by APIs with different route versions.

In `tools/list`, versioned tools expose `_meta.fastmcp.version: "1"` and
`_meta.fastmcp.versions: ["1"]`. Calls without a version select the highest
registered implementation. To pin a version, add `"fastmcp": {"version": "1"}`
to `params._meta`, alongside the existing protocol metadata; it is not a tool
argument. Unknown versions fail without falling back or contacting the API.
See [FastMCP versioning](https://gofastmcp.com/servers/versioning).

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
  -H 'Mcp-Method: tools/call' -H 'Mcp-Name: momentum_list_analyses' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"momentum_list_analyses","arguments":{"page_size":1},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"curl","version":"1"},"io.modelcontextprotocol/clientCapabilities":{}}}}'
```

Always check `result.isError`, not just HTTP 200.

### Discovery pagination

`DEFAULT_PAGE_SIZE` sets FastMCP's `list_page_size`: at most 100 components per
page by default, configurable from 1 to 100. It applies to `tools/list`,
`resources/list`, `resources/templates/list` and `prompts/list`. The current six
tools, one resource and one prompt each fit within their default discovery page.

When more components exist, the JSON-RPC result contains `nextCursor`. Pass this
opaque value unchanged as `params.cursor` in the next request for the same list
operation, with the usual request metadata. An absent cursor marks the last page;
pagination does not create an HTTP session.

The FastMCP client automatically retrieves all pages with `list_tools()` (and the
equivalent resource and prompt methods). For manual traversal, use
`list_tools_mcp(cursor=...)` and read `result.next_cursor`. See the
[FastMCP pagination documentation](https://gofastmcp.com/servers/pagination).
This setting controls component discovery; the analysis-result pagination
described below retains its existing contract.

## Reader migration

The Momentum tools use `/v1/analyses`, `/v1/analyses/latest`,
`/v1/analyses/{id}` and `/v1/recommendations`. Each list tool fetches exactly one
HTTP page and returns the existing typed `ReaderPage` directly in
`structuredContent`, with `items` and `next_page_token`.

| Tool | Filters | Default `page_size` | Maximum |
| --- | --- | --- | --- |
| `momentum_list_analyses` | Optional `ticker` | 50 | 100 |
| `momentum_latest_analyses` | Optional `ticker`, `rating` | 50 | 100 |
| `momentum_get_recommendations` | `rating`, default `Buy,Overweight` | 10 | 50 |

Each tool accepts `page_size` from 1 to its maximum above and `page_token` up to 512 characters,
empty for the first page. These bounds appear in the tool input schemas; invalid
values are rejected before any upstream request. Invalid `page_size` values return
a concise French tool error, for example `page_size doit être inférieur ou égal à 50.`
for recommendations. The `Field` constraints still generate the same `inputSchema`;
only their MCP error presentation changes. The MCP normalizes filters,
forwards the API cursor unchanged and returns the next cursor unchanged. It does
not decode tokens, keep pagination state or automatically load another page.
The API binds each cursor to its endpoint and normalized filters; reuse it with
the same tool and filters. An API-rejected token remains a tool error.

```python
page = await client.call_tool("momentum_list_analyses", {"ticker": "AAPL", "page_size": 20})
content = page.structured_content
# Read content["items"]. When more data is needed:
if content["next_page_token"]:
    page = await client.call_tool("momentum_list_analyses", {
        "ticker": "AAPL",
        "page_size": 20,
        "page_token": content["next_page_token"],
    })
```

Only an empty `next_page_token` ends the list. A short or empty page can still
carry a continuation cursor; a full page can be the last. Pagination does not
create an MCP session or a stable snapshot of data changing between requests.
The existing 45-second tool deadline and sanitized upstream errors still apply.

**Migration:** replace `limit` with `page_size` (maximum 100 for analyses, 50 for recommendations); `offset` is removed.
Follow API cursors instead of skipping an arbitrary number of results. Old
`limit`/`offset` arguments are rejected, not silently ignored. Read
`structuredContent.items` instead of `structuredContent.result`, and check
`structuredContent.next_page_token`. `momentum_latest_analyses` now returns one page,
not the whole catalogue. Update callers together with this MCP change; the HTTP
cursor format is unchanged. `/v1/recommendations` and its MCP tool now share a
maximum of 50; the other list endpoints retain 100. API and MCP constraints are
declared separately and must be updated together. Discovery pagination via
`DEFAULT_PAGE_SIZE` does not configure these analysis pages.

The resource `momentum://market_scanner/market-scans/latest` calls
`GET /v1/market-scans/latest` and returns the current reader envelope
as JSON text in `result.contents` from `resources/read`:
`{id, scan_date, created_at, report}`. `report` preserves the complete v3 data,
including decimal strings, null horizons and arbitration. Consumers of the old
flattened report must read `report.regime`, `report.summary`, `report.assets`.
The removed legacy `session_id` and `recommendation` fields are not fabricated.
The former `latest_market_scan` tool has been removed; consumers must use
`resources/read` with this URI. `resources/list` advertises the resource.

`prompts/list` advertises `momentum_analyze_ticker`; retrieve its instructions with
`prompts/get` and `{"name": "momentum_analyze_ticker", "arguments": {"ticker": "AAPL"}}`.
The prompt directs the client to consult existing analyses and read the market
resource, then summarize the evidence with dates and identifiers.

## Suggestions through Momentum API

`momentum_suggest_ticker` and `momentum_get_suggestion_status` call `POST /v1/suggestions` and
`GET /v1/suggestions/{uuid}` on the same `MOMENTUM_API_URL` as the analysis tools,
with the same Cloud Run identity and original HMAC caller assertion. Validation,
quotas, persistence and moderation belong to Momentum API, as in DeepCopy.
The MCP has no storage adapter, database credentials or separate moderation URL.
It cannot approve a suggestion or start an analysis.

The recovered routes are deployed in Momentum API. A live public MCP submission,
status read and duplicate submission returned the same persisted pending record.
The API owns the PostgreSQL transaction, quotas and moderation fields.

## Run and verify

### Local APIs with the remote database

From this service directory:

```sh
just up    # Momentum :8000 + Market Scanner :8003 + MCP :8080
just apis  # Only the APIs, if MCP already runs in another terminal
just run   # Only MCP
```

`Ctrl+C` stops the processes started by `up` or `apis`. The launcher refuses
occupied ports and stops the remaining processes if a service exits. It never
migrates or seeds a database. Its first run installs locked API dependencies
through `uv run --frozen`.

Create ignored `.env` files in both sibling API directories using their
`.env.example` files. Set `AUTH_MODE=token` and a distinct random `API_TOKEN`
of at least 16 characters for each API. Database configuration must use:

| API | Database | Login |
| --- | --- | --- |
| Momentum | `momentum` | `momentum_results_reader` |
| Market Scanner | `market_scanner` | `market_scanner_reader` |

Set each `DATABASE_URL` to its reader connection with
`?sslmode=verify-full&sslrootcert=/absolute/path/to/aiven-ca.pem`.
The administrator connection to `defaultdb` is not an API runtime connection.
Market Scanner uses `DATABASE_SCHEMA=_analysis`. Keep database credentials in
the API `.env` files; MCP does not receive them.

Set the same nonempty `SUGGESTION_HASH_SECRET` in Momentum API and MCP `.env`.
`just up` wires the MCP to loopback URLs and the API tokens from those files,
with IAM disabled locally. For a separately started `just run`, configure
`MOMENTUM_API_URL=http://127.0.0.1:8000`,
`MARKET_SCANNER_API_URL=http://127.0.0.1:8003`,
`MOMENTUM_API_USE_IAM=false` and the matching per-API tokens in MCP `.env`.
Restart an already-running MCP after changing its environment.

`/health` establishes process liveness only; authenticated `/ready` on each API
checks database access. These are live database connections: suggestion
submissions can create remote records. The simulation below uses disposable mocks.

### Automated verification

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
cover separate IAM audiences and round trips using the real Momentum API cursor
encoder and validator. The simulation checks two explicit pages per list tool
and exactly one upstream request per pagination call. Live IAM/data access needs
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
`config/constants.py` holds shared annotations, the analysis API version and
execution deadline; per-tool metadata lives beside the methods in `public_tools.py`.

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
