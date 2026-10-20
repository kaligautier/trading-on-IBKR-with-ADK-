# Implementation plan: Momentum ADK on dedicated Cloud Run

Status: validated by the user's “valid plan” on 2026-10-20.
Specification scope was validated on 2026-10-19. Prepare and review the execution
checklist before implementation, per the invoked spec-driven workflow.

Specification: [Momentum service](../docs/specs/momentum-service.md).
Previous plan: [public frontend archive](archive/public-frontend-plan.md).
Archive the preserved frontend `tasks/todo.md` before preparing the Momentum
execution checklist for review.

## Outcome and fixed decisions

Extract the complete existing Momentum ADK financial analysis workflow into
`apps/backend/momentum-adk`. Run one validated command per dedicated Cloud Run Job,
using only the existing LiteLLM gateway. Reuse the repository's current PostgreSQL
database, with an isolated `momentum` schema and dedicated `momentum_writer` login.
Keep consultation, public MCP, broker operations and historical imports outside
this release. Preserve the source's financial roles, tools and structured outputs.

Source baseline: DeepCopy `38d0736a4bf778ebcb81dbf4acef52fd2dd34e77`.
Target baseline: `origin/main` `9bbf5709b2895e2d0bdbd1d1667b860ddcfe43a8`, fetched
again before planning. Worktree: branch `docs/momentum-service-spec`.

## Architecture and dependencies

```mermaid
flowchart TD
  Caller[Authorized operator] --> HTTP[Private dispatcher]
  HTTP --> Job[Momentum Cloud Run Job]
  Job --> ADK[Existing Momentum ADK workflow]
  ADK --> Gateway[Existing private LiteLLM gateway]
  ADK --> Data[Market data providers]
  ADK --> PG[Existing PostgreSQL database: momentum schema]
  Migrate[Liquibase with migration identity] --> PG
```

The dispatcher and worker stay within the same application component and image,
with separate entrypoints and service accounts. The dispatcher has job-scoped
execution-with-overrides permission, no database/model secrets and no local worker
fallback. It returns an operation reference; the worker owns completion.

Dependency order:

1. Locked package and typed contracts enable isolated source ports.
2. Database privileges/session migrations and exclusive gateway transport are the
   early risk checkpoints; settle them before assembling the deployable workflow.
3. Output schemas, market-data tools and memory enable the original agent graph.
4. ORM/result writers, ADK session storage and model transport enable execution.
5. A completed local execution enables image/dispatcher verification.
6. Dedicated Terraform and passing CI enable image publication and reviewed rollout.

Work is sequential by default. Model and DB investigations are independent, but
their contracts must be settled before composition. No parallel agents are needed.

## Database design and proof

Use one logical database, not the source's automatically derived second database.
Business models explicitly name `momentum`; session connections use the fixed
`momentum, pg_catalog` search path. Both point to the existing database name with
the dedicated login. Secrets remain in Secret Manager, including the verified CA.

| Identity | Rights and ownership |
| --- | --- |
| Existing `database_migrator` | Owns schema/tables and applies reviewed Liquibase changes; never passed to a runtime. |
| `momentum_writer` | Non-owner LOGIN; INSERT plus necessary RETURNING reads on enumerated result tables; SELECT/INSERT/UPDATE/DELETE only on enumerated ADK session tables. |
| Private dispatcher | No PostgreSQL credential. |
| Independent verifier | Separate inspection credential for pilot reads; no wider runtime rights are added to support verification. |

The writer has no schema/database CREATE, CREATEROLE, CREATEDB, SUPERUSER,
BYPASSRLS, ownership, migration-role membership, TRUNCATE or grant option.
Do not grant privileges on every table across the database. Audit role membership,
default privileges and PUBLIC grants. PostgreSQL privileges are additive; a direct
REVOKE cannot negate a PUBLIC grant. Do not change shared grants blindly. See
[PostgreSQL GRANT](https://www.postgresql.org/docs/17/sql-grant.html) and
[schema isolation](https://www.postgresql.org/docs/17/ddl-schemas.html).

Liquibase owns business tables and the exact pinned ADK JSON session schema,
including indexes and version metadata. Existing Scanner changesets/checksums stay
unchanged. Add Momentum changesets to the shared root in dependency order.
Bootstrap extends existing installations; do not rerun initial Scanner bootstrap.
The user/admin creates the dedicated login and password through the existing
credential procedure; SQL files contain grants and role settings, not passwords.

Installed ADK 2.6.1 calls `prepare_tables()` and checks/creates missing tables and
indexes. Pin that SDK, provision its expected schema beforehand, and perform an
explicit read-only readiness check. Verify actual session creation, event writes,
resume and deletion using only the runtime role. Missing tables/indexes/version
must fail safely rather than require granting runtime DDL. If stock preparation
cannot satisfy this, stop at the DB checkpoint and review a narrow adapter; never
patch installed SDK files or silently elevate credentials.

Result persistence receives session/invocation metadata from `WorkflowExecution`
and commits it alongside the relational financial sections. Source rows lack these
fields; the adapter/schema change must preserve all financial outputs and permit
multiple results for the same ticker/date. Do not invent an idempotency guarantee.

Two pools (result/session), each size 1, `max_overflow=0`, finite acquisition/query
and idle deadlines, explicitly disposed on exit. Initial writer connection limit
4 leaves a small margin; verify against the existing PG capacity before rollout.
The schema owner can initialize migrations; the runtime must fail when asked to
CREATE/ALTER/DROP objects, including public or temporary objects.

## Exclusive inference transport

Adapt the existing Scanner's native Gemini gateway transport inside Momentum's own
package; do not import Scanner modules. Every collector, quick/deep analyst,
debate, manager and reflection node receives a gateway-backed model object.
Plain model-name strings must never silently resolve to a direct provider.

Require gateway URL and a Momentum-specific virtual key. Keep the key restricted
to approved model aliases/routes/budget. Reject missing/invalid configuration;
test timeout, denied key/model, malformed response and upstream error without
fallback. Do not configure Google API keys or direct Vertex credentials for model
calls. Keep gateway redirects disabled and sanitize errors, prompts and headers.
Pass network/subnet inputs from the existing private gateway deployment.

## Delivery sequence within CI limits

Every row is a proposed PR boundary, not the final implementation task checklist.
Only one application component may change in a PR; shared infra/database/workflow
files may accompany it. Target 600–850 counted lines where feasible, never more
than 1,000 additions plus deletions. The 859-line output-schema file needs a narrow
PR. Lockfile exclusions apply only to `uv.lock` and `package-lock.json`.

| Order | Reviewable slice | Expected counted size | Verification before next dependency |
| --- | --- | --- | --- |
| 0 | Validated spec and reviewed plan | Measure current diff | Policy tests, links and diff checks. |
| 1 | Package, request/value contracts, baseline lint/test CI | 600–850 | Locked install, request validation, package import. |
| 2 | Preserve complete financial output schemas | 900–980 | Typed examples, schema validation, no role/output removed. |
| 3 | Momentum bootstrap, grants and ADK session changesets | 650–900 | Real PG negative permissions; session lifecycle without DDL. |
| 4 | Result ORM models with explicit schema/correlation | 600–850 | Metadata/schema mapping and typed row construction. |
| 5 | Business Liquibase tables/indexes and migration tests | 600–900 | Reapply migrations; Scanner checksums and data unchanged. |
| 6 | Transactional result writers/repository | 650–850 | Complete financial sections, correlation, rollback, permissions. |
| 7 | Exclusive gateway model factory/settings | 600–850 | Real serializer against local HTTP responses, no direct fallback. |
| 8 | Storage, market-data configuration and stockstats primitives | 400–700 | Port relevant normalization/cache/indicator tests. |
| 9 | Existing Alpha Vantage adapters | 650–850 | Local provider HTTP fixtures, rate/failure handling. |
| 10 | Existing Yahoo adapters | 700–900 | Controlled provider responses, preserved output shape. |
| 11 | Vendor routing and ADK tool boundary | 450–750 | Routing/fallback tests; optional Scanner enrichment disabled. |
| 12 | Existing memory log and execution-memory service | 550–850 | Memory/reflection regression tests; ephemeral-path behavior. |
| 13 | Agent prompts, catalog and statistics | 450–750 | Every role uses the gateway; output schemas/statistics retained. |
| 14 | Workflow graph, runtime and session integration | 700–950 | Full graph with controlled providers, durable session and resume. |
| 15 | Application composition, worker and CLI | 500–850 | Full local command commits expected result; failures exit nonzero. |
| 16 | Private HTTP dispatcher and contract tests | 500–850 | 422/503/502/202 paths; correct per-execution job override. |
| 17 | Production image, smoke and CI security gates | 600–850 | Linux build; real boot; invalid worker command; dependency audit. |
| 18 | Dedicated Terraform foundation and job | 650–900 | Locked init/validate/mock tests; secrets, network, bounds and IAM. |
| 19 | Dispatcher Terraform, opt-in release workflow and operator guide | 650–900 | Private IAM, WIF permissions, digest publication and rollout checks. |

Sizes are estimates, not permission to exceed policy. Before each PR, recalculate
the whole diff against its actual base using the trusted scripts and GitHub file
counts. Split further if tests, fixtures or migrations exceed the budget. Use
stacked bases or land/rebase sequentially after review; do not open all cumulative
changes against main. Never work around policy by hiding code or altering limits.

Port tests only when their real dependencies exist; no skipped failing imports,
fake implementation placeholders or eager root-agent imports in partial libraries.
The first CI checks scoped library slices. Enable full graph checks when the graph
exists; enable image publication only when the complete worker is verified.

## Verification checkpoints

### A. Before workflow assembly

Disposable PG proves role isolation, same-database session storage, migration
repeatability and no runtime DDL. Gateway tests prove exclusively routed native
Gemini requests. A failure here blocks composition, not just release.

### B. Before image/release work

Run the complete preserved graph against controlled provider responses. Verify
typed final output, session/invocation correlation, transaction rollback and a
separate read of every expected relational section. Cover resume and worker errors.
Report mocked inference separately from a real model analysis.

### C. Before publication

Application lint/tests, dependency audit, Linux production image smoke, and all
affected Terraform/root workflows pass. Actions are SHA-pinned; PR jobs get no
cloud credentials. Add Momentum uv/docker/Terraform Dependabot coverage.
Dedicated Terraform state uses its own GCS prefix, with immutable image/secret
references and explicit job/service identities. No Terraform apply occurs in CI.

### D. Before claiming live completion

Review the exact Terraform plan for only intended resource changes, apply the
reviewed digest, verify anonymous denial and allowed dispatch, then track the
Cloud Run operation to a successful execution. Independently read the corresponding
financial result and ADK session from the existing database. Verify the Scanner
still works and that other schemas were not modified. An HTTP 202, ready service,
green mock test or image publication alone does not satisfy this checkpoint.

## Reproducible verification commands

Commands below describe the required implementation interfaces; new paths do not
exist yet. Local test variables are placeholders for disposable resources only.

```sh
python3 -m unittest discover -s .github/scripts -p 'test_pr_*.py' -v
git diff --check
cd apps/backend/momentum-adk
uv sync --frozen --python 3.12
uv run --frozen ruff check app tests scripts
uv run --frozen ruff format --check app tests scripts
TZ=UTC uv run --frozen pytest -q tests/unit
TZ=UTC MOMENTUM_TEST_ADMIN_URL=postgresql://postgres:local-test-only@127.0.0.1:55449/postgres MOMENTUM_TEST_CONTAINER=momentum-test-db uv run --frozen pytest -q tests/integration
uv export --frozen --no-dev --no-emit-project --format requirements-txt -o /tmp/momentum-requirements.txt
uvx --python 3.12 --from pip-audit==2.10.1 pip-audit --disable-pip --no-deps -r /tmp/momentum-requirements.txt
cd ../../..
docker build --platform linux/amd64 -t momentum:verify apps/backend/momentum-adk
uv run --project apps/backend/momentum-adk --frozen python apps/backend/momentum-adk/scripts/container_smoke.py momentum:verify
terraform -chdir=infra/momentum fmt -check -recursive
terraform -chdir=infra/momentum init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/momentum validate
terraform -chdir=infra/momentum test
```

Integration fixtures create an isolated database on the named disposable local
server, install the real shared Liquibase changelog, and authenticate separately as
runtime/migrator/verifier. Reject non-local URLs and existing fixture roles; require
the variables in the integration CI job instead of allowing skips. Start the server
on port 55449 using the repository's digest-pinned PostgreSQL test image and build
the existing database Liquibase image. The detailed checklist will record cleanup
and exact server-start commands without touching the real database.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| SDK silently creates session objects | Pinned version, migration readiness check and real restricted-role lifecycle tests before graph assembly. |
| PUBLIC/inherited grants bypass schema isolation | Audit effective privileges and fully qualified cross-schema/temporary writes; review shared-grant corrections before live changes. |
| Direct model access remains in a reflection node | Inject the gateway model everywhere and test graph-level outbound destinations. |
| Source tools perform network work or leak vendor errors | Controlled HTTP responses, bounded calls, sanitized exceptions and image tests without cloud access. |
| Long source files make PRs exceed policy | Measured narrow source ports, dependency-ordered PRs, no threshold edits. |
| Small PG connection allowance | Two one-connection pools, no overflow, role limit and explicit engine disposal; measure pilot use. |
| Multiple submissions overlap | No retry/exactly-once claim; one initial operator pilot, then explicit concurrency follow-up if needed. |
| Local memory mistaken for durable learning | Preserve source behavior but label filesystem memory ephemeral; results/sessions remain in PostgreSQL. |

## Execution checklist gate

The single-schema database design, delivery sequence and verification checkpoints
are validated. Prepare `tasks/todo.md`, sized to roughly five files per task, with
explicit acceptance and verification. Review that checklist before implementation,
as required by the invoked spec-driven workflow.
