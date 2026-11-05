# Specification: versioned HTTP resources and consumer migration

Status: implementation authorized by the user on 2026-11-04: "on s’en fou si ça casse on va a la cible". Proceed directly to the target without compatibility aliases or further phase approval gates.
Baseline: `origin/main` at `8a4dbb829e7f9d1477c8dd923e66724606d079dd`.
Prepared: 2026-11-04.

## Objective

Give every project-owned business HTTP operation an explicit major-version
contract, preserve HTTP semantics, and migrate every repository-owned consumer.
Deliver one pull request per affected component, with source, contract,
documentation, regression tests and CI evidence. Opening the PRs is the delivery
boundary; merging and deploying are separate actions.

The change is complete when the canonical business routes are versioned, all
owned callers use them, remaining unversioned paths are enumerated operational or protocol exceptions, and each component PR passes its relevant checks.
The removed business paths return 404 to authenticated callers; no redirect or fallback.

## Approved direction

1. `/v1` is the project convention for business resources. It is not a requirement
   imposed by RFC 9205 and is independent of package/OpenAPI metadata versions.
2. Breaking changes are explicitly accepted. Remove old business paths immediately
   and migrate all owned callers. No compatibility aliases, deprecation window or
   legacy fallback. Consumer deployment must accompany the provider release.
3. Health, readiness, documentation, schema and SDK/protocol-owned paths have
   different lifecycles. They are documented separately rather than mechanically
   rewritten under `/v1`.
4. Preserve authentication, authorization, persistence, quotas, report shapes,
   pagination semantics and provider protocols except for the explicit HTTP
   response improvements below.
5. No database migration, new dependency, live scan, provider call, merge or
   deployment is needed to deliver these PRs.

## References and HTTP policy

- [RFC 9205](https://www.rfc-editor.org/rfc/rfc9205.html): preserve generic HTTP
  semantics (§3.1); use links where useful (§3.2, §4.4); standard methods and
  status codes (§4.5–4.6); content types (§4.8); explicit cache policy (§4.9).
- [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html): method semantics,
  representation negotiation, HEAD, Allow, Location, 201 and 202 responses.

This specification applies those practices to this deployment. It does not claim
to define an Internet-wide namespace or to certify the entire application against
every HTTP RFC. The component PRs must identify the clauses and behavior they test.

Preserve the existing [Momentum HTTP profile](momentum-http-rfc-profile.md) and
[consultation contract](momentum-consultation-api.md). This specification extends
them with suggestion resources and a cross-component migration; it does not
replace the analysis validation, pagination, negotiation or security guarantees.

## Canonical contracts

| Component | Existing resource | Canonical contract |
| --- | --- | --- |
| Momentum API | GET `/v1/analyses`, `/v1/analyses/latest`, `/v1/analyses/{analysis_id}`, `/v1/recommendations` | Keep existing paths and semantics. |
| Momentum API | POST `/suggestions` | POST `/v1/suggestions`; successful durable creation returns 201 and Location identifying the new suggestion. Moderation remains pending. |
| Momentum API | GET `/suggestions/{suggestion_id}` | GET `/v1/suggestions/{suggestion_id}`; preserve response fields and access checks. |
| Scanner API | GET `/market-scans`, `/market-scans/latest`, `/market-scans/{scan_id}` | GET under `/v1/market-scans`; preserve report-v3, UUID validation, filters and cursor behavior. |
| Scanner ADK: owned operation | POST `/internal/daily-scan` | POST `/internal/v1/scan-jobs`; accepted dispatch returns 202 with the existing operation identifier, not a claim of scan completion. |

`/internal/v1/scan-jobs` names the submitted job resource collection. Do not invent
a local job-status URL unless it is actually implemented. Preserve the upstream
operation identifier so authorized operators can inspect the real operation.

### HTTP behavior and migration

- A canonical POST suggestion creates one durable suggestion and returns its
  canonical Location. Validate representation and authorization before writes.
- Remove the legacy suggestion, Scanner read and dispatch routes. Assert 404
  without side effects on authenticated requests to each old path.
- Every owned client, example, smoke check and collection uses canonical paths.
- Suggestion deduplication returns 200 for an existing record and 201 only for a
  record created by this transaction. Both responses identify the resource with
  Location; concurrent duplicates must not falsely claim creation.
- GET/HEAD never create suggestions or submit jobs. HEAD on owned read resources
  has no response body and preserves relevant GET status and headers.
- Unsupported registered methods return 405 with the appropriate Allow header.
  OPTIONS metadata, where supported, describes the actual resource methods and
  does not substitute for linked documentation.
- Preserve Momentum's content negotiation, query validation, problem responses,
  request IDs, conditional requests and cache behavior during route changes.
- Scanner v1 reads continue to return JSON and its existing documented error
  envelope. Reject an explicitly unacceptable representation with 406; preserve
  Bearer challenges and Allow headers. Keep its explicit no-store policy.
- Dispatch and creation responses are not publicly cached. Every introduced
  response representation has its correct Content-Type; no new custom version
  request header is introduced.
- Clients handle HTTP failures through their existing error paths, tolerate the
  documented success range, and never automatically retry a non-idempotent POST
  just because an old path might exist. No automatic legacy-path fallback.
- Canonical links respect the application's deployment base/root path. Tests
  cover a non-root mount where links are generated.

### Explicit exceptions

| Surface | Policy |
| --- | --- |
| `/health`, `/ready`, frontend `/health` | Operational interfaces, retained unversioned. |
| `/openapi.json`, `/docs`, `/redoc` where enabled | Tooling discovery paths, retained. |
| `/schemas/report-v3.json` | Versioned report representation, independent of the REST major version. |
| ADK `/run`, `/run_sse`, `/run_live`, `/apps/...`, discovery/debug/UI routes | Owned by the pinned ADK SDK; retain its contract and security middleware. |
| Public MCP POST `/` | Keep MCP protocol version negotiation and JSON-RPC contract; migrate its upstream HTTP calls. |
| LiteLLM `/v1beta/models/...`, `/key/...`, `/team/...` | Provider/administration protocol contracts; retain upstream-compatible paths and the existing proxy allowlist. |
| Momentum ADK job | No HTTP API to version; update its Scanner HTTP consumer. |

## Component deliverables

Every implementation branch starts from a freshly fetched `origin/main`, in its
own worktree; no stashing or modification of the user's existing checkout.
The repository permits at most one application component per PR.

| PR component | Deliverable and affected contract |
| --- | --- |
| `apps/backend/momentum-api` | Versioned suggestions, HTTP policy and schema alignment, Location, removed-path regression checks, OpenAPI export, saved requests, tests and README; include this shared specification. |
| `apps/backend/market-scanner-api` | Versioned read routes, removed-path regression checks, HEAD/method/negotiation checks, smoke checks and README. |
| `apps/backend/market-scanner-adk` | Versioned job submission, correct asynchronous acknowledgement, removed-path checks, authentication/admission and dispatch tests. |
| `apps/backend/momentum-public-mcp` | Canonical suggestions and Scanner URLs; gateway tests, simulations, mocks and README aligned without changing public tool schemas. |
| `apps/backend/momentum-adk` | Canonical Scanner URL in market-data tool, client regression coverage. |
| `apps/frontend` | Canonical Scanner reader URL and client tests; preserve rendering behavior. |
| `infra/market-scanner` | Scheduler points to the canonical job-submission endpoint; Terraform assertions and operator documentation. |

Momentum uses two dependent PRs (paths, then creation semantics) to keep the
generated OpenAPI change within the 1000-line gate: eight PRs in total.
PRs are stacked in component order so each diff contains one component while
consumer CI sees the candidate providers. The real MCP-to-PostgreSQL CI check
moves from the provider workflow to the MCP workflow, retaining triggers on
provider and database changes. The test itself is preserved.

Provider PRs must be available before their consumer deployments. Each PR will
state these dependencies. A local combined integration check must use the exact
candidate commits; isolated mocks are insufficient to prove combined routing.

## Tech stack and structure

Use the committed lockfiles: Python 3.12, FastAPI/Starlette, Pydantic, pytest,
HTTPX, Ruff and mypy where configured; the public MCP uses FastMCP. Frontend:
Next.js 16.4.1, TypeScript, Node's test runner. Infrastructure: Terraform.

- HTTP providers: `apps/backend/*/src/app/`.
- Momentum HTTP boundary: `presentation/routes/` and `presentation/http/`.
- MCP consumer: `momentum-public-mcp/src/momentum_public_mcp/gateway.py`.
- Job consumer: `momentum-adk/app/components/tools/market_data.py`.
- Frontend reader: `apps/frontend/src/lib/market-scanner/`.
- Tests: provider `src/test/`, MCP/job `tests/`, frontend colocated `*.test.ts`.
- Contracts: existing OpenAPI, Postman artifacts, component README files.
- This specification: `docs/specs/rest-api-versioning.md`.
- After spec approval: implementation plan `tasks/plan.md`, tasks `tasks/todo.md`.

Those task files currently record completed database runtime reliability work.
Archive both under `tasks/archive/` before preparing the new plan, preserving the
historical implementation and verification evidence.

## Code style

Keep thin HTTP handlers, typed service boundaries, existing naming conventions,
88-column Python formatting and current Ruff complexity limits. For example:

```python
router = APIRouter(prefix="/v1/market-scans", tags=["market-scans"])


@router.get("/latest", response_model=MarketScanResponse)
async def latest(service: Service) -> MarketScanResponse:
    return assemble(await service.latest_scan())
```

Avoid a cross-component shared package for a small routing convention. Do not
perform unrelated formatting or replace established HTTP policy code wholesale.
Read the frontend's installed Next.js documentation as its AGENTS.md requires
before changing frontend code.

## Commands and verification strategy

Commands below run from each component directory unless a root-relative path is
shown. Install with committed locks; record environment failures separately.

Python setup: `uv sync --frozen --python 3.12`.
API lint: `uv run --frozen ruff check src scripts` and
`uv run --frozen ruff format --check src scripts`.
API types: `uv run --frozen mypy src/app`.
API unit tests: `uv run --frozen pytest -q src/test/unit`.
Momentum schema: `uv run --frozen python scripts/export_openapi.py --check`.
Momentum integration: `bash scripts/test_database.sh verify -q` on disposable DB.
Scanner integration: `uv run --frozen pytest -q src/test/integration`, with a
disposable TEST_DATABASE_URL configured as in `scanner-reader.yml`.
Scanner ADK: `TZ=UTC uv run --frozen pytest -q src/test/unit`.
Public MCP: `uv run --frozen ruff check src tests scripts` and
`uv run --frozen pytest -q`; `uv run --frozen python scripts/simulation.py`
against local mock services using the existing simulation setup.
Momentum ADK: `uv run --frozen ruff check app tests` and
`TZ=UTC uv run --frozen pytest -q tests/unit`.
Frontend: `npm ci`, `npm test`, `npm run lint`, `npm run typecheck`,
`npm run build` from `apps/frontend`.
Terraform, from repo root: `terraform -chdir=infra/market-scanner fmt -check`,
`terraform -chdir=infra/market-scanner init -backend=false -input=false -lockfile=readonly`,
`terraform -chdir=infra/market-scanner validate`,
`terraform -chdir=infra/market-scanner test`.
All PRs: `git diff --check`, component-scope and size gates, existing relevant CI.

Tests must verify behavior, not just string replacements: canonical requests
reach services; removed paths return 404 without dispatch or writes;
invalid/authentication/method/negotiation failures retain their status and headers;
Location resolves to a readable resource; HEAD has no body; job dispatch occurs
once and returns 202 only after upstream acceptance. Add route-inventory checks
for all owned business paths and an explicit exception list.

Consumer tests must check outbound canonical paths and unchanged payloads,
pagination, authentication and failure handling. Exercise the candidate MCP and
frontend readers against candidate provider routes locally without live cloud
credentials. Never invoke a billable scan to test a route rename.

## Boundaries

- Always: preserve existing dirty worktrees; write regression tests; update
  contracts and callers; test before commits; report local, CI and remote evidence
  separately; link this spec and dependencies in each PR.
- Ask first: database schema changes, new dependencies, unrelated CI changes,
  changing the explicit protocol exceptions.
- Never: commit secrets, edit vendor code, hide failing tests, bypass PR scope
  gates, use production mutations as fixtures, merge or deploy without authorization.

## Acceptance checklist

- [x] User authorizes the target with immediate breaking changes.
- [x] Record plan and tasks; proceed under the user’s explicit instruction.
- [ ] All canonical owned business routes use the agreed versioned paths.
- [ ] Removed business paths return 404; no aliases or fallback remain.
- [ ] Every owned consumer and executable example uses canonical paths.
- [ ] HTTP behavior above has meaningful passing regression coverage.
- [ ] OpenAPI, documentation, collections and runtime routes agree.
- [ ] Candidate providers and consumers pass combined local integration checks.
- [ ] One scoped PR per listed component is pushed and open; relevant CI passes.
- [ ] The original checkout remains unchanged by this work; no stash is created.

## Review decision

The user rejected temporary compatibility and instructed immediate implementation
of the target. Record implementation evidence in tasks/todo.md and component PRs.
