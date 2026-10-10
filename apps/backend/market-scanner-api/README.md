# Market Scanner consultation API

Independent, read-only FastAPI microservice for persisted market scans. The request
path is router → service → repository; response assembly lives in `app/dto/response`.
It does not invoke ADK, call a model, run a scan or migrate the database.

## HTTP contract

All data and documentation routes require authentication.

| Method and path | Result |
| --- | --- |
| `GET /market-scans/latest` | Most recently persisted run, ordered by `created_at DESC, id DESC` |
| `GET /market-scans?page_size=20&page_token=…` | Run summaries and `next_page_token` |
| `GET /market-scans/{scan_id}` | One persisted run by UUID |
| `GET /schemas/report-v3.json` | Canonical JSON schema for the `report` field |
| `GET /openapi.json` | API schema |
| `GET /health` | Public process liveness, no database call |
| `GET /ready` | Authenticated database read/permission check |

Latest and detail responses contain `id`, `scan_date`, `created_at`, and `report`.
`report` is the writer's persisted **v3 market regime object**, including asset
values, decimal strings, nullable horizons, provenance and data quality. The service
validates it against the bundled writer serialization schema and preserves it.
It does not fabricate legacy signals, probabilities or other absent fields.
This is an adapted v3 contract, not a drop-in replacement for older consultation DTOs.
Internal worker session IDs are not exposed in the response envelope.

History returns `{ "items": [...], "next_page_token": "..." }`; each summary has
`id`, `scan_date`, `created_at`, `regime` and `summary`. It lists **all runs**, including
multiple runs on the same date. `page_size` defaults to 20 and accepts 1–100.
Follow the opaque token until it is empty. The keyset order handles tied timestamps
and newly inserted latest runs without shifting subsequent pages. Tokens are
versioned positions, not authorization credentials; they do not provide snapshot
isolation against arbitrary backdated inserts or deletions. No costly total count
or full reports are included in history.

Errors use `{ "error": { "code": "...", "message": "..." } }`:

- `401 UNAUTHENTICATED`: missing/incorrect local bearer token.
- `404 SCAN_NOT_FOUND`: no latest scan or unknown UUID; an empty list returns 200.
- `422 INVALID_ARGUMENT`: invalid UUID, page size or cursor.
- `503 STORE_UNAVAILABLE`: database failure, timeout or missing schema.
- `500 INVALID_STORED_REPORT`: stored JSON does not satisfy the v3 contract.

Responses set `Cache-Control: no-store` and `X-Request-ID`. Structured completion
logs include correlation ID, route template, status and duration, without request
bodies, bearer tokens, database URLs or query parameters. Uvicorn access logs are
disabled. Storage failure logs include a safe exception category.

## Database and authentication

Use the existing Aiven PostgreSQL **`market_scanner` schema** and
**`market_scanner_reader` role**. The existing Liquibase changeset in
`database/changelog/market-scanner/001-initial.sql` already grants only SELECT.
Runtime SQL is schema-qualified, parameterized and uses read-only transactions.
The service never receives administrator, migrator or writer credentials.

One process owns one connection by default (`DATABASE_POOL_SIZE=1`, maximum 2,
no overflow). Pool wait defaults to five seconds; connection and statement timeouts
are ten seconds. Dispose the pool through the FastAPI lifespan. Keep deployment
replicas, revision overlap and other readers within the existing role connection
limit of four. Increasing workers multiplies the pool; the image starts one worker.

Remote database URLs must use `sslmode=verify-full`; provide the Aiven project CA
through `sslrootcert=/etc/database/ca.pem`. Only localhost can disable TLS.
Unknown/repeated URL options and non-reader database usernames are rejected.
Secrets belong in environment variables/Secret Manager, never checked-in files.

- Local/default `AUTH_MODE=token`: require `API_TOKEN` of at least 16 characters.
  All routes except `/health`, including OpenAPI/docs, require `Authorization: Bearer …`.
- Cloud Run `AUTH_MODE=cloud_run`: relies on the **Cloud Run IAM frontend** to verify
  Google identity tokens. Application token authentication is then disabled. The
  supplied Terraform explicitly enables the invoker IAM check and grants only
  named callers. This mode refuses to start without `K_SERVICE`; that check alone
  is not authentication and must not be used to expose the container directly.

See [the isolated deployment root](../../../infra/reader/README.md).

## Local development

From this directory, create an ignored `.env` from `.env.example`, replace the
placeholder token/password, then run:

```sh
uv sync --frozen --python 3.12
uv run --frozen uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8080 --no-access-log
curl -H "Authorization: Bearer $API_TOKEN" http://127.0.0.1:8080/market-scans/latest
```

The curl command expects `API_TOKEN` in your shell environment. For Aiven, also
supply the reader URL with verified TLS and a locally downloaded project CA.

## Verification

```sh
uv run --frozen ruff check src scripts
uv run --frozen ruff format --check src scripts
uv run --frozen mypy
uv run --frozen pytest src/test/unit -q
```

Integration tests **fail** when `TEST_DATABASE_URL` is absent. They recreate the
scanner schema and grants and must use a disposable localhost PostgreSQL database
whose name ends with `_test`. Never point them at an existing application database.

```sh
docker run --rm -d --name reader-postgres -p 127.0.0.1:55447:5432 \
  -e POSTGRES_PASSWORD=integration-only -e POSTGRES_DB=scanner_reader_test postgres:17-alpine
TEST_DATABASE_URL=postgresql://postgres:integration-only@localhost:55447/scanner_reader_test \
  uv run --frozen pytest -q
docker stop reader-postgres

docker build -t local/market-scanner-api:review .
uv run --frozen python scripts/container_smoke.py
```

Tests execute the checked-in migration DDL and grants on real PostgreSQL, test
read-only permissions, cross-schema isolation, exact report preservation,
keyset pagination under concurrent inserts, missing data and storage failures.
The container check boots the production image and checks HTTP authentication
and the packaged schema. CI also checks Terraform and runtime dependencies.

The API has no runtime dependency on the writer. CI detects schema drift by
running `scripts/check_report_schema.py` with the writer's Python environment and
`PYTHONPATH=apps/backend/market-scanner-adk/src` from the repository root. Regenerate
`src/app/schemas/report-v3.json` from `MarketRegime.model_json_schema(mode="serialization")`
only after reviewing compatibility and updating the reader tests.

Design references: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/),
[Google AIP-158 pagination](https://google.aip.dev/158) (inspiration, not a claim of
full AIP conformance), and [Aiven TLS verification](https://aiven.io/docs/platform/concepts/tls-ssl-certificates).
