# Spec: Momentum internal consultation API

Status: implementation authorized by the user on 2026-10-22 through the request
to implement this specification and create a merge request. Production rollout
remains a separate checkpoint; this delivery prepares reviewed code and artifacts.
The user requested strict RFC alignment on 2026-10-22. The companion
[HTTP RFC inventory and profile](momentum-http-rfc-profile.md) defines applicable
standards, explicit project choices and verification responsibilities.

## Objective

Extract DeepCopy's Momentum consultation capability into an independent backend
product at `apps/backend/momentum-api`. Authorized consumers can discover persisted
analyses, inspect a financial decision and its supporting reports, and retrieve
the latest recommendations without knowing ADK or the relational database layout.
A future MCP will consume this HTTP contract as an adapter; it will not query SQL
or reproduce selection, filtering or financial mapping logic.

Implementation scope retained from the specification:

1. One dedicated Momentum API, separate from the Scanner API and Momentum worker.
2. Consultation only; no job submission, suggestions, administration or broker work.
3. Service-to-service access to a shared analysis catalogue; no end-user tenancy.
4. Deliver an independently buildable/testable/deployable service, including CI and
   Terraform. Deployment and live acceptance remain separate checkpoints.
5. No MCP implementation, frontend migration or historical DeepCopy data import.

User outcomes:

- Find the analyses available for a ticker and distinguish repeated runs.
- Read a dated recommendation together with its supporting financial sections.
- Discover the latest persisted result for each ticker, including non-buy ratings.
- Connect a future MCP using documented operations, inputs and error codes alone.

## Inspected baseline and extraction scope

Target checkout: `84196d3937fa677ddefb81013943665a27e02eba`.
DeepCopy source: `38d0736a4bf778ebcb81dbf4acef52fd2dd34e77`, inspected locally.
Both checkouts contain unrelated uncommitted files; preserve them.
These are source observations, not a claim about current deployed services.

| Existing evidence | Treatment in this product |
| --- | --- |
| DeepCopy `momentum-api/src/app/routes/analyses.py` | Extract history, latest-per-ticker, detail and recommendations. |
| DeepCopy query service, repository, mapper and response DTOs | Preserve financial meanings and field names; adapt storage and harden contracts. |
| DeepCopy history uses offset without explicit ordering | Replace with deterministic ordering and bounded keyset pagination. |
| DeepCopy latest joins on `MAX(created_at)` per ticker | Resolve timestamp ties by UUID so exactly one result wins per ticker. |
| DeepCopy detail uses generic JSON objects | Define explicit nested response models and documented nullability. |
| Target `momentum-adk/app/infrastructure/models.py` and result repository | Read committed results in database `momentum`, schema `_analysis`; all sections are written transactionally. |
| Target `database/momentum-unified-bootstrap.sql` | Existing runtime grants cover writers; add a separate reader through reviewed database changes. |
| Target `market-scanner-api/README.md` | Reuse structure, connection limits and response assembly; the RFC profile supersedes its custom errors and validation statuses for this new API. |
| DeepCopy public MCP tools | Four consultation use cases inform this API; Scanner and suggestion tools remain excluded. |

Keep the worker specification [momentum-service.md](momentum-service.md) intact:
this is its separate consultation follow-up. Preserve the existing Momentum
`tasks/plan.md` and `tasks/todo.md`; archive them only when this spec is approved
and the next plan is prepared. Do not copy DeepCopy's Alembic history or admin API.

## Proposed HTTP contract

JSON API, prefix `/v1`; operation IDs are explicit and stable. This is a new
contract, not a drop-in replacement for the legacy bare lists and offset inputs.
The existing DeepCopy frontend/MCP will not be redirected in this release.

| GET path | Operation ID | Successful result |
| --- | --- | --- |
| `/v1/analyses` | `list_analyses` | Paginated summaries of all persisted runs; optional `ticker`. |
| `/v1/analyses/latest` | `latest_analyses` | Paginated latest summary for every ticker; optional `ticker` and `rating`. |
| `/v1/analyses/{analysis_id}` | `get_analysis` | One detailed result by UUID. |
| `/v1/recommendations` | `get_recommendations` | Paginated latest-per-ticker summaries filtered by `rating`. |
| `/health` | `health` | Process liveness without database/model calls. |
| `/ready` | `ready` | Authenticated database connectivity and required read-permission check. |
| `/openapi.json` | — | Authenticated machine-readable contract. |

All listed resources also support HEAD and OPTIONS as defined in the HTTP profile;
HEAD returns the GET metadata without content, and OPTIONS describes allowed
methods. These operations preserve the route's authentication requirement.

History and latest use `page_size=20`, recommendations uses `page_size=10`;
all accept 1–100 and optional `page_token` (maximum 512
characters). Response: `{ "items": [...], "next_page_token": "..." }`, with
an empty string at the end. The page size limits each response, not the total
number of accessible results. History includes every retained run since the
beginning, including repeated runs for the same ticker/date; no implicit date
window applies. Latest includes only the latest persisted run of each ticker.
Both views sort by `created_at DESC, id DESC`. Tokens are versioned and bound
to the endpoint and normalized filters. Reject malformed tokens and endpoint or
filter changes. They are positions, not
credentials or snapshots; arbitrary backdated inserts/deletions can change results.

For latest, select one winner per ticker by `created_at DESC, id DESC` before
applying the rating filter, cursor and page size. Exhausting pages traverses all
tickers when the dataset is unchanged. If a ticker receives a new result between
requests, its winner can move ahead of the cursor and be missed in that traversal;
restart from the first page for a refreshed view. Do not promise a frozen snapshot.

Recommendations uses the same pagination envelope and latest-per-ticker selection,
then rating filters, global ordering, cursor and page size. It has the same
concurrent-update limitations as latest. This harmonization is a project choice,
not an RFC pagination mandate. A newer Sell must never expose an older Buy as a
recommendation. There is no ranking by profitability, score or confidence.

Normalize tickers using the writer's existing trim/uppercase and 1–32 character
validation rules, without importing the worker package. `rating` is a nonempty
comma-separated subset of `Buy,Overweight,Hold,Underweight,Sell`, normalized
case-insensitively and deduplicated; reject unknown values. Latest has no default
rating filter; recommendations defaults to `Buy,Overweight`. An absent rating
does not become Hold. Unknown ticker and empty catalogue return 200 with no items.

### Financial response model

Retain DeepCopy's `AnalysisSummaryResponse` field set: identity, ticker, dates,
provider, portfolio recommendation and levels, trader levels, selected technical
indicators and fundamentals. Dates use RFC 3339 full-date strings, creation time
uses an RFC 3339 UTC timestamp with `Z`, and UUIDs use RFC 9562 hyphenated strings.
Creation time is required. Preserve stored finite numeric values and nulls, never
fill missing market values with zero or recalculate a recommendation.
Non-finite numbers or otherwise unserializable stored values are invalid stored
data, not silently converted to null. Emit UTF-8 JSON conforming to RFC 8259.

Detail retains `id`, `ticker`, `analysis_date`, `created_at`, model/provider names,
next-analysis metadata, and the existing sections: `technical_indicators`,
`fundamentals`, `sentiment` with items, `news` with items, `research_plan`,
`trader_proposal`, `portfolio_decision`, `debate_arguments` and `run_stats`.
Use explicit nested DTOs matching the reviewed DeepCopy mapper field set; no
implicit ORM serialization or arbitrary dictionary contract. Preserve aliases
such as `macd_signal`, sentiment item `score`, debate `round` and `conviction`.
Absent single sections are null, absent collections are empty. Stable child order
uses persisted IDs as tie-breakers, including debate type/round/role ordering.
Unknown future database columns do not automatically enter HTTP responses.

Expose only result data, not `user_id`, `session_id`, `invocation_id`, ADK events,
prompts, credentials or SQL rows. Keep `analysis_date`, `created_at` and
`next_analysis_date` distinct: latest persisted does not imply current market data.
No synthetic freshness score or silent refresh. Reports remain data for the future
MCP; they cannot authorize tool execution or change its access rules.

### Errors and compatibility

Application errors adopt RFC 9457 Problem Details with media type
`application/problem+json`, replacing the initial custom error envelope.
Use stable documented problem-type URIs, a title, matching HTTP status, sanitized
detail and extension `code`. Clients use the type as the primary problem identifier.
The [HTTP profile](momentum-http-rfc-profile.md) specifies bodyless exceptions,
content negotiation, challenges, conditional reads and metadata requirements.

| Status | Code / meaning |
| --- | --- |
| 400 | `INVALID_ARGUMENT`: invalid UUID, ticker, rating, page size or cursor; also reject nonempty read request bodies. Malformed authentication has its own Bearer `invalid_request` challenge. |
| 401 | Missing/unsupported credentials: Bearer challenge without body or OAuth error. Invalid token: Bearer `invalid_token` challenge and `UNAUTHENTICATED` problem when content is permitted. |
| 404 | `ANALYSIS_NOT_FOUND`: valid UUID with no result. |
| 405 | `METHOD_NOT_ALLOWED`: recognized method disallowed on the resource; include `Allow`. |
| 406 | `NOT_ACCEPTABLE`: no acceptable representation under the chosen negotiation policy. |
| 412 | `PRECONDITION_FAILED`: failed conditional read. |
| 503 | `STORE_UNAVAILABLE`: temporary database unavailability or timeout. |
| 500 | `INVALID_STORED_ANALYSIS`, `STORE_CONFIGURATION_ERROR` (missing schema/denied reader grants), or `INTERNAL_ERROR`: sanitized, correlated failure. |

Unknown routes return a 404 `NOT_FOUND` problem. Framework validation must use
the documented 400 profile rather than FastAPI's default 422 for these bodyless
reads. This is a contract decision consistent with HTTP semantics, not a claim
that every use of 422 is forbidden. Unimplemented HTTP methods follow 501 semantics.
Cloud Run IAM may reject requests before the application with its own 401/403
body; clients must not assume that edge errors follow Problem Details.
Reads have no side effects. Consumers may retry transient 503s with bounded backoff;
invalid input/authentication and corrupt stored data require correction.
Use `Retry-After` only when a meaningful retry delay is known; it is not required
on every 503. Successful conditional reads may return a bodyless 304.
Additive optional fields are compatible; breaking changes require a new version.

## Architecture, storage and authentication

Request path: router → query service → repository; typed response assembly at the
HTTP boundary. The runtime imports neither `momentum-adk` nor `market-scanner-api`.
It has no ADK, LiteLLM, market-data, Cloud Run job or broker client dependency.
Read already committed `_analysis` results, using parameterized schema-qualified
queries, bounded result sets and read-only transactions. No N+1 summary loading.

Proposed dedicated login: `momentum_results_reader`. Grant only CONNECT to
`momentum`, USAGE on `_analysis`, SELECT on explicitly enumerated result tables.
No access to `_sessions`, Scanner, LiteLLM or migration metadata, no DML/DDL/TEMP,
ownership, inherited administrative grants or writer credentials. Add forward-only
Liquibase grants/index changes; do not edit applied changesets. No runtime migrations.
Check query plans on representative synthetic data before choosing extra indexes.

One HTTP process, pool size one, no overflow, pool wait five seconds, SQL/connect
deadline ten seconds; dispose the engine via FastAPI lifespan. Use verified TLS
and the existing CA mechanism for remote PostgreSQL. Bound deployment instances
and revision overlap to the independently reviewed reader connection budget.

Local mode requires a bearer token on data, readiness and documentation routes;
only process liveness is exempt. Real bearer credentials require verified HTTPS,
including local manual use. Cloud mode requires Cloud Run IAM invoker checks,
explicit caller service accounts, no anonymous grants, and audience-bound identity
tokens. No auth bypass based merely on a request header. The future MCP receives
only invocation rights, not database secrets. Its public/user authentication is a
separate future design; this API trusts authorized service identities to read the
shared catalogue. Tenant isolation would require a new specification.

Use a dedicated `infra/momentum-api` root/state and service account. Reference
immutable image digests and numeric Secret Manager versions, preserving the
existing worker/Scanner resources. Keep secrets out of Terraform values/state.
Set `Cache-Control: no-store` and the documented custom `Request-ID` header.
The RFC profile defines ETags, content negotiation and conditional reads; no-store
does not disable those semantics. Log route template, status,
duration and safe failure category without financial payloads, tokens or DB URLs.

## Tech stack and project structure

Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 async, asyncpg, Uvicorn, uv;
pytest/pytest-asyncio, Ruff and strict mypy. Match compatible Scanner conventions
and generate a dedicated lockfile during implementation. Exact dependency
versions and container digests are to be resolved and audited in the plan, not
copied from the legacy lock without checking. No new shared runtime package.

Proposed paths, not yet implemented:

```text
apps/backend/momentum-api/
  src/app/                  Factory, configuration, routes, DTOs, service, repository
  src/test/unit/            Validation, mapping, route and error contracts
  src/test/integration/     Real migrated PostgreSQL and effective role permissions
  scripts/                  Contract export, disposable DB and container verification
  openapi.json              Deterministic export of FastAPI's contract
  pyproject.toml, uv.lock    Independent dependency ownership
  Dockerfile, README.md      Runtime image and operational instructions
infra/momentum-api/         Dedicated Terraform root and tests
database/changelog/         Additive reader grants/index migrations
.github/workflows/          Dedicated application/infrastructure verification
docs/postman/               Reusable local requests/examples; preserve old collection
```

FastAPI models/routes are the executable source of truth; CI compares their
generated OpenAPI to the checked-in export. Examples must cover populated/empty
lists, absent optional sections, missing IDs and errors. Adapt a separate set of
Postman consultation requests to v1, without replacing existing worker/Scanner
requests. No workspace provisioning or publication is needed for this spec.

## Commands

Available now, from repository root, for this documentation change:

```sh
git diff --check
python3 -m unittest discover -s .github/scripts -p 'test_pr_*.py' -v
```

Required interface after the implementation supplies the proposed package/scripts
(these commands have not been run and do not work in the current checkout):

```sh
uv sync --project apps/backend/momentum-api --frozen --python 3.12
cd apps/backend/momentum-api
uv run --frozen ruff check src scripts
uv run --frozen ruff format --check src scripts
uv run --frozen mypy src/app
uv run --frozen pytest src/test/unit -q
bash scripts/test_database.sh verify
uv run --frozen python scripts/export_openapi.py --check
uv build --out-dir dist
uv run --frozen uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8002 --no-access-log --ssl-certfile "$API_TLS_CERT_FILE" --ssl-keyfile "$API_TLS_KEY_FILE"
```

The database script must create/verify only its labelled disposable localhost
database, apply the real Liquibase schema and reader grants, run integration tests,
and clean up its own resources. It must refuse external database targets.
Dev expects ignored local `DATABASE_URL` and `API_TOKEN` configuration, with a
reader login, and local TLS certificate/key paths in `API_TLS_CERT_FILE` and
`API_TLS_KEY_FILE`. Clients must trust the development CA and verify the local
server identity. Examples contain placeholders or disposable test values only.

From repository root, after image/infrastructure files exist:

```sh
docker build --platform linux/amd64 --tag local/momentum-api:verify apps/backend/momentum-api
uv run --project apps/backend/momentum-api --frozen python apps/backend/momentum-api/scripts/container_smoke.py local/momentum-api:verify
terraform -chdir=infra/momentum-api fmt -check
terraform -chdir=infra/momentum-api init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/momentum-api validate
terraform -chdir=infra/momentum-api test
```

## Code style

Use explicit imports, typed protocols, snake_case, English documentation,
88-column Ruff formatting and no configuration/network work at import time.
Keep HTTP handlers thin and DTO assembly separate. Existing Scanner pattern:

```python
@router.get("/{scan_id}", response_model=MarketScanResponse)
async def get_scan(scan_id: UUID, service: Service) -> MarketScanResponse:
    return assemble(await service.get_scan(scan_id))
```

Apply this style to Momentum's own types; never import the sibling application.

## Testing strategy and success criteria

1. Unit/HTTP tests cover every operation, validation boundary, null section and
   Problem Details response. Implement the companion RFC profile's acceptance
   checks for HEAD/OPTIONS, challenges, negotiation and conditional requests.
   OpenAPI exposes stable operation IDs, headers, statuses and typed financial DTOs.
2. Real disposable PostgreSQL tests exercise actual Liquibase tables and grants,
   repeated ticker/date runs, timestamp ties, stable history cursors and the
   newer-Sell/older-Buy exclusion. Verify that both history and latest can traverse
   more than 100 results across pages on an unchanged dataset, including filtered
   recommendations, with exactly one winner per ticker for latest views.
   Cover winner replacement between pages and reject
   cross-endpoint cursors. Empty queries return 200; unknown UUID returns 404.
3. Synthetic writer-shaped fixtures round-trip every exposed financial field and
   alias, with nulls preserved and internal correlation excluded. Schema drift
   checks run in CI; the runtime never imports the writer.
4. Prove denied INSERT/UPDATE/DELETE/DDL/TEMP and cross-schema reads using the
   actual reader role, including inherited/PUBLIC privileges. Verify connection
   release and sanitized failures on missing schema or timeout.
5. Container checks boot the production image and exercise authentication and
   packaged OpenAPI. No live models, paid analysis or cloud credentials in PR CI.
6. Require at least 90% combined line/branch coverage on this new API, with real
   integration tests mandatory rather than silently skipped. Test meaningful
   behavior, not implementation details or copied assertions.
7. Terraform tests reject anonymous access and mutable images/secrets. Record
   publication, reviewed plan/apply and live checks independently of local tests.
8. Live acceptance, when deployed: anonymous/unauthorized invocation denied;
   an allowed identity reads a known persisted analysis whose identity and exposed
   values match an independent storage read. No writer/model/job activity occurs.
9. Every PR changes one application component and at most 1,000 counted lines,
   preserving repository policy. Dependency-ordered PR boundaries belong to PLAN.
10. Delivery report includes working commands, contract, test evidence and remaining
    live prerequisites. A future MCP is an external consumer, not an acceptance
    dependency for this API release.

## Boundaries and open decisions

- Always: preserve dirty files, keep the source checkout untouched, validate
  inputs, minimize database privileges, retain provenance, verify field fidelity,
  and distinguish local tests, CI, deployment and live evidence.
- Ask first: validate this spec, then its plan, then tasks before implementation;
  resolve a shared backend versus dedicated API, launch/admin scope, tenancy,
  compatibility requirements or broader schema/data migration before dependent work.
  Approved plan details do not require repeated routine confirmations.
- Never: expose the API anonymously, copy secrets/customer data, migrate historical
  records implicitly, edit applied migrations, issue orders, generate analyses on
  a read, weaken PR gates, or publish/merge/deploy as a side effect of specification.

Review decisions: confirm the dedicated consultation-only product and shared
catalogue assumptions; accept the versioned contract with paginated history,
latest-per-ticker views and recommendations. The user requested both the
latest-per-ticker view and full history on 2026-10-22, then strict RFC alignment.
If legacy consumer compatibility is required,
specify it before finalizing the contract. The initial draft has no live rollout
authorization and no specified latency SLO; measure query behavior during planning
before committing a performance target.

Technical references checked while drafting:
[Cloud Run service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service),
[PostgreSQL ordering and DISTINCT](https://www.postgresql.org/docs/current/sql-select.html),
[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/).
