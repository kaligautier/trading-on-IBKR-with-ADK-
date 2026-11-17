# Versioned REST resources: path migration

Authorized 2026-11-04: the user explicitly accepts breaking changes and requests
implementation of the target, without legacy aliases or further approval gates.

## Objective and target

Own business resources use /v1. Momentum suggestions move to /v1/suggestions
and /v1/suggestions/{suggestion_id}; Scanner reads move to /v1/market-scans;
Scanner job submission moves to /internal/v1/scan-jobs. Remove old business paths.
Migrate public MCP, Momentum job, frontend and Scheduler consumers. Retain health,
readiness, documentation, schema and vendor protocol paths as explicit exceptions.

RFC 9205 guides HTTP semantics and links; /v1 is a project convention, not an RFC
requirement. Preserve auth, pagination and representation contracts. The following
Momentum slice adds 201 for actual creation, 200 for existing suggestions and
Location; Scanner submission acknowledges acceptance with 202.

## Structure and style

Use existing src/app/presentation/routes and presentation/http boundaries;
regressions live in src/test. Keep typed thin handlers and existing Ruff style:
`router = APIRouter(prefix="/v1/suggestions", tags=["suggestions"])`.

## Commands and tests

From apps/backend/momentum-api: `uv sync --frozen --python 3.12`,
`uv run --frozen pytest -q src/test/unit`, `uv run --frozen ruff check src scripts`,
`uv run --frozen ruff format --check src scripts`,
`uv run --frozen python scripts/export_openapi.py --check`.
Full persistence checks: `bash scripts/test_database.sh verify -q`.
Verify old routes return 404, new paths preserve methods/auth, and OpenAPI agrees.

## Delivery and boundaries

One application component per PR and at most 1000 changed lines. Momentum needs
two slices because of the generated OpenAPI move. Stack PRs so consumer checks
see matching providers. Move the existing MCP/PostgreSQL CI invocation to the MCP
workflow with provider/database triggers; preserve its test. Publish PRs with
checks, without merging or deploying. Always preserve dirty worktrees and use
local disposable fixtures; never commit secrets or execute real scans. No DB
schema or unrelated CI changes. CI-required patch updates to existing
lockfile packages are recorded in the delivery evidence. The full target specification and
reviewed implementation tasks accompany the Momentum semantics slice.
