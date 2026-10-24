# Momentum consultation API

Private, read-only service over committed results in `momentum._analysis`.
FastAPI models/routes and HTTP policy define the executable contract;
[openapi.json](openapi.json) is its deterministic export.
The [product specification](../../../docs/specs/momentum-consultation-api.md)
and [RFC profile](../../../docs/specs/momentum-http-rfc-profile.md) explain the scope.

## Operations

| GET resource | Meaning |
| --- | --- |
| `/v1/analyses` | Every retained run; optional `ticker`. |
| `/v1/analyses/latest` | One latest run per ticker; optional `ticker`, `rating`. |
| `/v1/recommendations` | Same latest selection, default ratings `Buy,Overweight`. |
| `/v1/analyses/{analysis_id}` | One analysis with typed financial sections. |
| `/health` | Process liveness; no authentication or database dependency. |
| `/ready` | Authenticated connectivity and SELECT access to all required tables. |
| `/openapi.json` | Authenticated executable contract. |

Each resource supports HEAD and OPTIONS. OPTIONS returns 204 and
`Allow: GET, HEAD, OPTIONS`; this does not enable browser CORS.
All reads have no side effects on the store and cannot dispatch analyses.

Lists use `page_size` (1–100, default 20; recommendations 10) and `page_token`
(maximum 512 characters). Envelope: `{"items": [], "next_page_token": ""}`.
An empty token means the end. Pass the next token with the same endpoint and
normalized filters; page size can change. Both history and latest order by
`created_at DESC, id DESC`. UUID breaks exact timestamp ties deterministically;
it does not establish chronology. Latest selects the winner before rating filters.
An older Buy never replaces a newer Sell. Filters accept canonical ratings
`Buy,Overweight,Hold,Underweight,Sell`, case-insensitively, comma-separated.
Tickers are trimmed and uppercased. Unknown ticker returns an empty page.

Pagination is not a snapshot. Changes can move a new winner ahead of a cursor;
restart at page one to refresh. History includes repeated ticker/date runs and
has no implicit date window. Optional financial sections remain null, collections
remain empty, and unknown stored numbers are not replaced by zero.
Execution/session/user correlation is excluded from responses.

## Package organization

- `domain/analyses`: financial values and normalized search criteria.
- `services`: consultation use cases.
- `ports`: interfaces required by those use cases.
- `adapters/postgresql`: connection, SQL projections and stored-result mapping.
- `presentation`: HTTP routes, response DTOs, mapping and protocol policy.
- `config/settings.py`: validated runtime configuration.
- `main.py`: runtime composition and resource lifecycle.

Dependencies point toward the domain: services use `ports/analysis_reader.py`,
PostgreSQL adapters implement that contract, and routes translate domain results
through `presentation/mappers.py` into explicit public DTOs. HTTP status mapping
lives only in `presentation/http/errors.py`. Storage projections enumerate SQL
columns independently in `adapters/postgresql/projections.py`. Architecture tests
prevent core modules from importing presentation or concrete storage adapters.
Unexpected-error diagnostics contain a request ID, exception class and application
module/line only; raw exception messages, source lines and local values are omitted.

## Local development

From this directory:

```sh
uv sync --frozen --python 3.12
uv run --frozen ruff check src scripts
uv run --frozen ruff format --check src scripts
uv run --frozen mypy src/app
uv run --frozen pytest src/test/unit -q
bash scripts/test_database.sh verify --cov=app --cov-branch --cov-fail-under=90
uv run --frozen python scripts/check_storage_contract.py
uv run --frozen python scripts/export_openapi.py --check
uv build --out-dir dist
```

The database command owns only a labelled disposable PostgreSQL container on
`127.0.0.1:55473`; it refuses an existing container, applies real Liquibase
migrations, runs unit/integration tests and removes its container on exit.
`start` and `stop` expose the same fixture for diagnosis. Integration tests fail
without explicit fixture opt-in; they never silently skip.

Copy `.env.example` to ignored `.env`, set a dedicated reader URL/token and use
a locally trusted TLS certificate/key for real manual credentials. Export the TLS
paths in your shell; loading `.env` in Python cannot populate shell arguments:

```sh
export API_TLS_CERT_FILE="$PWD/certs/localhost.pem"
export API_TLS_KEY_FILE="$PWD/certs/localhost-key.pem"
uv run --frozen uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8002 \
  --no-access-log --ssl-certfile "$API_TLS_CERT_FILE" --ssl-keyfile "$API_TLS_KEY_FILE"
```

Use a development CA trusted by your client; do not disable verification.
Disposable fixture credentials over isolated test transports prove application
behavior only. There is no configuration/network work at module import time.
The packaged runtime owns one engine/pool and closes it on shutdown.

[Postman requests](../../../docs/postman/momentum-api.postman_collection.json)
use `momentum_api_base_url`, `api_token` and `analysis_id`. Configure a known
retained UUID for the detail request. Leave secrets in local environment/secret
variables. An unknown-ID test assumes its all-ones UUID is absent.
Run with `postman collection run <collection-path> --no-report-events`; the
container smoke command supplies a synthetic retained analysis and disposable token.

## Authentication, storage and operation

Local mode requires one `Authorization: Bearer <opaque-token>` on every resource
except liveness. Tokens must have at least 16 characters. No tokens in URLs/bodies.
Cloud Run mode relies on Google's enforced IAM ingress: the separate Terraform
root enables invoker checks, grants only explicit identities and leaves anonymous
access disabled. The `K_SERVICE` startup check is a configuration guard, not
identity verification. Do not expose the container directly in this mode.
A future MCP uses its own Cloud Run identity when invoking this API; external
MCP user access tokens are not passed through to this backend.

The reader login is `momentum_results_reader`, database `momentum`, schema
`_analysis`. Remote URLs require `sslmode=verify-full`; custom CA URLs also use
`sslrootcert=/etc/database/ca.pem`. Pool size is 1, overflow 0, pool wait 5 seconds,
SQL/connect timeout 10 seconds. Reads use repeatable-read read-only transactions.
Each list loads four summary tables in batches, independent of page length;
detail loads the eleven typed financial tables. Readiness checks every table.

The current Aiven baseline includes the reader's grants and consultation indexes.
Provision all domain logins privately and use the domain's
[`bootstrap.sql`](../../../database/domains/momentum/bootstrap.sql) for a fresh installation.
Follow the [database guide](../../../database/README.md) to verify or adopt an existing
database as `database_migrator`. The current changelog has no pending consultation
migration and requires no context filter. No runtime DDL is permitted.

The dedicated `infra/momentum-api` root references immutable image digests and
numeric secret versions. Configure the reader database URL and CA in Secret
Manager privately. Keep URL/token values out of Terraform. Production image
publication, migration, Terraform plan/apply and live IAM/TLS/data verification
are separate release steps; local tests do not establish a deployed release.

## HTTP behavior and problems

Success JSON is UTF-8. Accept both `application/json` and
`application/problem+json`; unsupported success representations give 406.
For `application/json`, a syntactically valid `charset` parameter in `Accept`
has no effect ([RFC 8259 section 11](https://www.rfc-editor.org/rfc/rfc8259.html#section-11));
output remains UTF-8. Quality weights still apply: an explicit JSON `q=0`
overrides a wildcard even when `charset` is present. Other representation
parameters, such as an unknown `profile`, are not ignored.
Identity is the only content coding. All responses use `Cache-Control: no-store`
and a server-generated `Request-ID`. Successful GET/HEAD responses carry a strong
ETag of the exact JSON bytes. `If-Match` uses strong comparison before
`If-None-Match` weak comparison, giving 412 or bodyless 304. Authentication,
validation and not-found errors precede conditional evaluation. HEAD never
contains response content. Date preconditions and Range are ignored: no
Last-Modified authority or range support is offered. No CORS policy is installed.

All GET/HEAD resources reject unknown or repeated query parameters with 400
before accessing the reader. Only the three list endpoints accept query
parameters; detail, health, readiness and OpenAPI accept none. Authentication,
unknown-resource and method errors retain precedence. OPTIONS reports capabilities
without validating query parameters.

Problem type URIs use this README's stable anchors. Status matches the HTTP
status. Content is omitted if `application/problem+json` or identity is excluded;
required headers/status remain. Missing credentials give a bodyless 401 with
`WWW-Authenticate: Bearer realm="momentum-api"`; invalid credentials add
`error="invalid_token"`. The managed Cloud Run edge has its own rejection format.

### invalid-argument
400: malformed path/query/conditional inputs, duplicate/unknown parameters or a
nonempty GET/HEAD body. Correct the request; retries without changes do not help.

### invalid-request
400: malformed or multiple credential transports. Bearer `invalid_request` challenge.

### invalid-token
401: invalid local credential. Bearer `invalid_token` challenge; obtain a valid token.

### analysis-not-found
404, `ANALYSIS_NOT_FOUND`: unknown retained UUID.

### not-found
404, `NOT_FOUND`: unknown resource. An unknown ticker remains an empty 200 page.

### method-not-allowed
405: recognized method unavailable on this resource; consult `Allow`.

### not-acceptable
406: the offered success representation/content coding is excluded by the client.

### precondition-failed
412: `If-Match` did not match the current representation. Refetch before retrying.

### invalid-stored-data
500: a stored result violates the typed financial contract, including nonfinite
numbers or duplicate singleton sections. Requires operator/data investigation.

### configuration-error
500: missing schema/columns, failed authentication or insufficient storage grants.
Requires operator intervention; no SQL or connection details are returned.

### store-unavailable
503: connectivity, pool wait or SQL timeout. Retry with bounded backoff.
No fixed Retry-After is promised because recovery time is unknown.

### internal-error
500: unexpected server failure. Logs contain safe route/status/duration only;
financial payloads, credentials, raw URLs and driver exceptions are excluded.
The returned Request-ID and safe failure code are logged for correlation.

### not-implemented
501: the HTTP method is not implemented by this service.

## Operational evidence

Request and unexpected-failure events are emitted as single-line JSON with UTC
`timestamp`, `severity`, `event` and server-generated `request_id`. Completed
requests include the route template, HTTP status, safe category and duration.
Diagnostics contain code locations and exception classes, not raw exception
messages, source lines, locals, request URLs, tokens or financial values.
Python logging-internal traceback output is disabled at runtime bootstrap;
a broken logging sink does not replace the HTTP outcome.

A valid version-00 W3C `traceparent` adds `trace_id` and `parent_span_id` for
correlation with upstream traces. Zero, malformed, unsupported or repeated values
are ignored. These fields never authenticate a caller and are not local span IDs.
The service creates no spans and configures no OpenTelemetry exporter or collector.
See [W3C Trace Context](https://www.w3.org/TR/trace-context/) and the
[OpenTelemetry log data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/).

Storage and mapping failures retain their original causes internally while the
HTTP boundary returns the existing sanitized problems. Shutdown always attempts
to dispose the pool. If cleanup also fails during a primary lifecycle failure,
the primary failure is preserved and cleanup is reported with a safe JSON event.
A standalone cleanup failure remains a failed shutdown.

Tests inject settings with dotenv disabled and explicit deployment options;
`app.main:create_app` still loads runtime settings when invoked without arguments.
A synthetic poisoned environment/dotenv test verifies the injection boundary.
