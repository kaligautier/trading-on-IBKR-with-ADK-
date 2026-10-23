# Spec: dedicated Momentum analysis service

Status: scope validated on 2026-10-19; plan validated by the user on 2026-10-20.
The user authorized checklist execution on 2026-10-20 ("mtn on implement").
Reviewed source: DeepCopy commit `38d0736a4bf778ebcb81dbf4acef52fd2dd34e77`.
Target baseline: `origin/main` at `9bbf5709b2895e2d0bdbd1d1667b860ddcfe43a8`.

## Objective

Bring the existing Momentum analysis engine into this repository as an independent,
privately invokable service with dedicated Terraform-managed Cloud Run resources.
An authorized operator submits one ticker analysis, tracks the Cloud Run execution,
and independently verifies the persisted result. The existing Scanner keeps working.

The first release covers analysis execution and persistence. A consultation API and
public MCP are separate later releases. Do not expose either through this service.

## Validated scope and implementation decisions

1. Extract `momentum-adk`, running one analysis per Cloud Run Job, with dedicated
   Terraform. Do not port the full administration API. Keep the private dispatcher
   minimal and in the same application component.
2. Route every model call exclusively through the existing LiteLLM gateway with a
   dedicated Momentum virtual key. No direct Gemini/Vertex path or fallback.
3. Reuse the existing PostgreSQL service with one dedicated `momentum` database,
   following the user's final 2026-10-20 clarification. ADK tables live in
   `_sessions`; financial result tables live in `_analysis`. Keep distinct
   non-owner runtime logins with access only to their own schema. Scanner and
   LiteLLM remain unchanged. Remove the superseded test-only Momentum databases
   and legacy shared schema after backup and verification, as explicitly authorized.
4. Delivery includes reproducible code, image, Terraform and CI. A live rollout is
   a separately reported checkpoint after the exact image and plan are reviewable.

## Inspected source and differences

Paths below are relative to the DeepCopy source repository unless marked target.

| Evidence | Consequence |
| --- | --- |
| `apps/backend/momentum-adk/DESIGN_SPEC.md`, `app/application.py`, `app/job_runner.py` | Preserve direct ADK execution, transactional result persistence and nonzero failure exits; no SQL polling queue. |
| `app/domain/contracts.py` | Reuse `AnalysisRequest`, `WorkflowExecution`, `WorkflowResult` and analyst validation. |
| `app/services/runtime.py` | Preserve persistent ADK sessions and explicit resume invocation IDs in the dedicated Momentum database and `_sessions` schema. |
| `app/config/settings.py`, `app/components/agents/momentum/catalog.py` | Source uses native Google models. LiteLLM routing is an explicit adaptation. |
| `app/infrastructure/models.py`, `app/infrastructure/result_writer.py` | Preserve the structured financial result contract and its relational mapping. |
| `apps/backend/momentum-api/alembic/versions/` | Historical migrations also manage unrelated domains. Extract only reviewed Momentum dependencies. |
| `apps/backend/momentum-api/src/app/adapters/cloud_run.py` | Dispatch uses per-execution `TA_ANALYSIS_REQUEST` environment overrides. |
| `app/components/tools/market_data.py` | Optional Scanner read currently has no Cloud Run IAM authentication. Leave disabled unless adapted and verified. |
| `infrastructure/cloud_run.tf` | Source worker uses a six-hour timeout, mutable secret versions and image drift exclusion. Do not copy these deployment choices blindly. |
| Target `database/README.md`, `database/domains/momentum/changelog.yaml` | Liquibase owns the domain schemas; runtime identities do not create business tables. |
| Target `apps/backend/market-scanner-adk/src/app/config/llm.py` | Existing native Gemini gateway transport is a reference; do not import the sibling application at runtime. |

The source contains approximately 5,944 application and 976 test Python lines.
These counts exclude packaging, non-Python resources and infrastructure. A complete
extraction cannot fit one PR under the target repository's policy.

## Runtime and API contract

Proposed topology: authorized caller → private Cloud Run HTTP dispatcher → dedicated
Cloud Run Job → ADK workflow → PostgreSQL results and persistent ADK sessions.
Both runtimes belong to `apps/backend/momentum-adk`, using one isolated package.
The same image may run different entrypoints. The dispatcher must not execute the
workflow in its HTTP process or require database credentials.

Proposed private endpoints, to be finalized in the API contract before coding:

| Operation | Behavior |
| --- | --- |
| `GET /health` | Process readiness only; no model or database calls. |
| `POST /internal/analyses` | Validate one request, dispatch one worker, return HTTP 202 with session UUID and Cloud Run operation name. |
| Invalid request | HTTP 422; no worker execution. |
| Missing dispatcher configuration | HTTP 503; no local background fallback. |
| Dispatch failure | HTTP 502 with a stable sanitized error; no request payload or provider response. |

Reuse the domain request fields: normalized ticker, analysis date, selected analyst
roles, requester label, session UUID, optional resume invocation ID, output language
and bounded debate counts. The HTTP input excludes internal `past_context`
and `pending_outcomes`; the application derives those. Generate a session UUID
when absent. A requester label is audit context, never authorization.

The proposed initial operator request uses one debate round and one risk round.
Preserve typed results, analyst roles, tools and workflow ordering; do not replace
Momentum with a simplified agent under the same name.

HTTP 202 establishes dispatch acceptance only. Report the operation resource name
as an operation, not as a completed execution. A worker succeeds only after its
typed result is persisted. Resume uses the explicit session/invocation contract.
Disable automatic job retries. Do not claim deduplication or exactly-once execution:
parallelism one applies within an execution, not across several submissions.

Cloud Run IAM protects invocation, with explicit allowed principals and no anonymous
binding. The dispatcher identity may run only its own job with overrides. That
requires `run.jobs.runWithOverrides`; plain `roles/run.invoker` is insufficient.
Choose the narrowest applicable job-scoped grant and test it. See the official
[Cloud Run permissions](https://docs.cloud.google.com/iam/docs/roles-permissions/run)
and [job execution contract](https://docs.cloud.google.com/run/docs/reference/rest/v2/projects.locations.jobs/run).

Keep the local API contract under version control. FastAPI-generated OpenAPI is the
runtime source of truth; examples and tests must agree with it. Do not bootstrap or
publish a Postman workspace merely for this extraction.

## Tech stack

- Python 3.12, uv, Google ADK 2.6.x, Pydantic 2, SQLAlchemy 2 and asyncpg; generate
  and commit a dedicated `uv.lock`. Align exact compatible versions during planning.
- Existing Momentum market-data dependencies and prompt resources, retained only
  where used; FastAPI/Uvicorn for the proposed private dispatcher.
- Existing Gemini-compatible LiteLLM transport with a Momentum-specific credential
  and explicit quick/deep model configuration. No direct-provider fallback.
- Existing PostgreSQL service, with one `momentum` database, `_sessions` and
  `_analysis` schemas, and bounded, independently credentialed pools.
- Terraform 1.14.4 in CI, compatible with the repository's supported 1.x range;
  Google provider constraints aligned with existing roots and a committed lockfile.
- Linux amd64 production image with digest-pinned bases and a non-root runtime user.

## Project structure

Proposed new paths; none exist as implementation in this draft:

```text
apps/backend/momentum-adk/
  app/                         Domain, workflow, tools, persistence and adapters
  tests/                       Ported tests and new boundary/integration tests
  scripts/container_smoke.py    Offline production-image verification
  pyproject.toml, uv.lock       Independent locked dependencies
  Dockerfile, .dockerignore     Independent build context
  justfile, README.md           Repeatable commands and operator guide
infra/momentum/                Dedicated runtime/state root and mock-provider tests
database/domains/momentum/    Current baseline, bootstrap and future migrations
.github/workflows/momentum.yml Application, dependency, image and Terraform gates
docs/specs/momentum-service.md This specification
```

Archive the old frontend plan before replacing `tasks/plan.md` in the dedicated
Momentum worktree. Preserve the existing frontend checklist until the task phase;
archive it before preparing the Momentum `tasks/todo.md` after plan approval.

## Commands

Existing executable policy checks from the target repository root:

```sh
python3 -m unittest discover -s .github/scripts -p 'test_pr_*.py' -v
terraform fmt -check -recursive infra
git diff --check
```

Required commands after the corresponding implementation slice exists:

```sh
cd apps/backend/momentum-adk
uv sync --frozen --python 3.12
uv run --frozen ruff check app tests scripts
uv run --frozen ruff format --check app tests scripts
TZ=UTC uv run --frozen pytest -q
cd ../../..
docker build --platform linux/amd64 --tag momentum:verify apps/backend/momentum-adk
uv run --project apps/backend/momentum-adk --frozen python apps/backend/momentum-adk/scripts/container_smoke.py momentum:verify
terraform -chdir=infra/momentum init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/momentum validate
terraform -chdir=infra/momentum test
```

Integration jobs must provision disposable PostgreSQL and required mocks, then run
the full applicable suite without silently skipping database tests. The plan must
supply the exact integration command, migrations and environment variable names.

The local development command will bind only to localhost:

```sh
uv run --project apps/backend/momentum-adk --frozen uvicorn app.main:app --app-dir apps/backend/momentum-adk --host 127.0.0.1 --port 8005
```

## Code style

Preserve small adapters, typed Pydantic contracts, constructor injection and
snake_case names. Use English documentation/comments, 88-column Ruff formatting
and explicit imports. A source pattern to retain:

```python
async def execute(self, request: AnalysisRequest) -> WorkflowExecution:
    execution = await self._execution_service.execute(request)
    await self._result_repository.save(execution.result)
    return execution
```

Avoid sibling-service imports, speculative shared packages, whole-repository copy
operations, and incidental refactoring. Retain relevant license/provenance notices.

## Infrastructure and data boundaries

- Separate `infra/momentum` backend prefix, dedicated service accounts, names and
  labels; no adoption or deletion of existing DeepCopy resources.
- Private dispatcher with scale-to-zero, maximum one instance and short dispatch
  timeout. Initial proposed worker limit: 2 vCPU, 4 GiB, 1 task, parallelism 1,
  no automatic retry and a 1,800-second timeout. Validate these limits in a pilot;
  do not assume the source's six-hour limit is needed.
- Reference immutable image digests and numeric secret versions. Never ignore
  image drift. Secrets are provisioned outside Terraform values/state.
- Limit secret access to the worker's database/session/gateway requirements; the
  dispatcher needs no database or model secret. Reuse the gateway network through
  explicit inputs. Provision a separate Momentum key, never the gateway master key.
- Liquibase's existing migration role owns the `_sessions` and `_analysis` schemas and their tables.
  `momentum_results_writer` and `momentum_sessions_writer` are non-owner logins
  without superuser, database creation,
  role creation, bypass-RLS or migration-role membership. Its rights are restricted
  to explicitly enumerated tables in their own schema: result INSERT and
  necessary RETURNING reads; session SELECT/INSERT/UPDATE/DELETE required by ADK.
  Revoke PUBLIC CONNECT/TEMP on `momentum`; deny cross-schema access.
  No table ownership,
  schema/database CREATE, TRUNCATE, grant option or access to other domain tables.
- Use the corresponding `_sessions` or `_analysis` search path, with an explicit schema on business
  ORM metadata. Search path is routing, not authorization: prove isolation through
  grants and negative permission tests, including fully qualified table names.
- Prepare the pinned ADK session tables, indexes and version metadata through
  Liquibase. The Job receives only runtime credentials and checks migration
  readiness before work; it must not create tables/indexes or migrate on startup.
  Configure both database URLs explicitly; never derive a second URL by changing
  a database name or silently fall back to the legacy application database.
- Audit effective PUBLIC and inherited privileges, not only direct grants. Deny
  writes outside Momentum, including temporary/public objects. If an existing
  database-wide PUBLIC grant permits those writes, assess the impact and review
  its correction before rollout rather than claiming a role-level REVOKE fixes it.
- Bound each SQLAlchemy pool to one connection with no overflow, close engines on
  exit, set query/idle deadlines and a conservative role connection limit. Verify
  TLS/CA settings and secret redaction on both result and session connections.
- Persist session and invocation correlation with the financial result in the
  same transaction; the source result rows currently omit that correlation.
- Do not replay the whole DeepCopy Alembic history or migrate historical data.
  Verify TLS/CA handling for both connections and bounded database pools.
- Local memory files/cache remain ephemeral on Cloud Run. PostgreSQL results and
  sessions are durable; cross-execution learning is not guaranteed by local files.
- Leave optional Scanner enrichment disabled initially. Enabling it requires a
  fixed URL, timeouts, sanitized errors and an audience-bound service ID token;
  see [service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service).

## CI and delivery constraints

The trusted default-branch checks enforce at most one application component and
at most 1,000 added plus deleted lines per PR. Only `uv.lock` and `package-lock.json`
are excluded; Terraform locks, tests, prompts, workflow and documentation count.
Several small commits in one oversized PR still fail.

Use a sequence of dependency-ordered PRs, each independently checkable. Exact file
groups and sizes belong to the next, human-reviewed plan. Measure cumulative PR
diffs against their actual base, including documentation. Do not change thresholds,
hide source in generated artifacts, or exempt imports to bypass these rules.

Port contracts, tools, workflows and persistence in bounded slices, introducing
entrypoints only when their dependencies exist. Incomplete libraries must pass
their scoped checks and remain unavailable for deployment. Never publish an image
whose full execution path is incomplete. Keep HTTP worker code in one component;
any later `momentum-api` belongs to a separate component and PR sequence.

The Momentum workflow must check locked installation, Ruff, offline tests, runtime
dependency auditing, Linux image build/smoke, and Terraform fmt/init/validate/mock
tests. Pin external actions by SHA, keep PR permissions read-only and avoid cloud
credentials or model calls in PR jobs. Include new uv/docker/Terraform directories
in Dependabot. Existing affected workflows must continue to pass.

Image publication is opt-in, restricted to reviewed main-branch commits after all
required checks, using WIF and an explicit release environment. Publication does
not apply Terraform. Record the source SHA and immutable image reference.

## Testing strategy

- Port existing meaningful domain, workflow, statistics, resume and persistence
  tests. Add regression coverage for boundaries changed during extraction.
- Offline tests cover ticker/request validation, no dispatch on invalid input,
  dispatch failure, safe error output, missing configuration, gateway failure
  without fallback, final structured result, and nonzero worker failure exit.
- Exercise the real ADK graph against controlled provider responses. For tests
  that run actual HTTP integrations, use local HTTP mocks and record the guarantees;
  distinguish those checks from unit-level stubs and live inference.
- Disposable PostgreSQL verifies migration compatibility, complete result reads,
  transaction rollback, resume/session storage and actual role permissions. Prove
  the writer cannot read/write Scanner or Liquibase tables, cannot write public
  objects, create/alter/drop tables, or obtain migration rights. Verify result
  writes and ADK session CRUD still work without runtime DDL privileges.
- Image checks prove package resources/imports, dispatcher readiness and worker
  failure on a missing/invalid command without cloud or model access.
- Terraform tests reject anonymous access, mutable images/secrets, broad IAM and
  incorrect job overrides permissions; assert resource bounds and state isolation.
- No existing project-wide coverage percentage is claimed for Momentum. Preserve
  the source test cases and cover the changed failure paths; settle any numeric
  threshold in the plan rather than silently weakening another service's gate.

## Boundaries

- Always: preserve dirty worktrees, keep source untouched, maintain the spec,
  validate inputs, retain attribution, run relevant checks and distinguish local,
  mocked, CI and live evidence. Keep changes within the approved extraction.
- Ask first: validate the specification, plan and tasks at the skill's required
  gates; resolve database placement, inference mode or scope changes before their
  dependent work. Dependency/CI additions described here become authorized with
  the approved plan; routine implementation needs no repeated permission.
- Never: commit credentials/state/customer data, weaken CI policy, auto-merge,
  place broker orders, mutate portfolios, expose the execution service publicly,
  or present health/HTTP 202/mock tests as completed analysis proof.

## Success criteria

1. Momentum runs from its own package/image with no runtime source-checkout or
   sibling-application dependency, preserving the existing analysis behavior.
2. An allowed caller submits one valid request; invalid input starts no worker;
   anonymous invocation is denied in the deployed environment.
3. A completed pilot worker produces a validated financial result and persistent
   ADK session. An independent database read verifies the expected ticker, date,
   session correlation and populated financial sections.
4. Model/database/dispatch failures are visible and sanitized; a failed run cannot
   be reported as a completed analysis. Worker failures exit nonzero.
5. Dedicated Terraform resources/state, exact image digest, pinned secrets and
   least-privilege identities pass configuration tests and reviewed live planning.
6. Every PR satisfies both trusted CI policies and its application/infrastructure
   checks. Existing Scanner functionality remains verified after affected changes.
7. No historical data migration, consultation endpoints, public MCP or public
   analysis trigger is included. Those follow-ups can use the persisted contract.
8. Report implementation readiness, CI, publication, apply and live pilot as
   separate outcomes. If rollout prerequisites are unavailable, explicitly leave
   the corresponding live criteria pending.
9. Results and sessions use `_analysis` and `_sessions` in one `momentum` database.
   Their dedicated runtime roles cannot access each other's schema or write outside
   their own enumerated tables; runtime DDL is denied and tested.
10. Every quick, deep and reflection model uses LiteLLM. A missing gateway or
    gateway failure never causes a direct Gemini/Vertex request.

## Review gates

- Scope, exclusive LiteLLM and reuse of the existing PostgreSQL database with
  schema/user isolation: validated by the user's answers on 2026-10-19.
- Plan in `tasks/archive/momentum-worker-plan.md`: validated by the user's “valid plan” on 2026-10-20.
- Momentum task checklist in `tasks/archive/momentum-worker-todo.md`: implementation authorized by the
  user on 2026-10-20 ("mtn on implement").

Do not advance to implementation before those gates have been validated.
