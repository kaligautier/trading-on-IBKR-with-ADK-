# Momentum execution checklist

Status: implementation authorized by the user on 2026-10-20 ("mtn on implement").
T01–T11 and T09a completed locally; PostgreSQL foundation verified; CI and later tasks are tracked separately.
Scope validated 2026-10-19; [plan](plan.md) validated by the user on 2026-10-20.
Specification: [Momentum service](../docs/specs/momentum-service.md).
Previous checklist: [frontend archive](archive/public-frontend-todo.md).

## Execution rules

Run tasks in dependency order. Each task changes at most five listed files;
initializers and fixtures count. Split a task before adding more files. PR numbers
refer to plan sequence numbers, not GitHub numbers. Group related tasks into their
proposed PR, then measure the whole PR against its actual base: one application
component and at most 1,000 added plus deleted lines. Only generated `uv.lock` and
`package-lock.json` are excluded. Split further whenever the measured diff requires.

Use incremental implementation and test-driven development for behavior changes.
Port meaningful source tests with their dependencies; never skip broken imports,
remove financial roles/outputs, or publish an incomplete runtime to make checks pass.
Record each task's results/commit in its PR. Re-run affected existing checks after
shared database/infra changes. Keep source and dirty worktrees intact. No automatic
merge or unreviewed live apply.

File prefixes: `P/` = `apps/backend/momentum-adk/`; `D/` = `database/`;
`F/` = `infra/momentum/`; other paths are relative to the repository root.
These are proposed paths, not claims of existing implementation.

## Executable verification helpers

Run from the repository root after package bootstrap:

```sh
momentum_project=apps/backend/momentum-adk
u() { uv run --project "$momentum_project" --frozen pytest -c "$momentum_project/pyproject.toml" -q "$momentum_project/tests/unit/$1"; }
i() { uv run --project "$momentum_project" --frozen pytest -c "$momentum_project/pyproject.toml" -q "$momentum_project/tests/integration/$1"; }
lint() { uv run --project "$momentum_project" --frozen ruff check --config "$momentum_project/pyproject.toml" "$momentum_project/app" "$momentum_project/tests"; }
```

Integration checks require the disposable PostgreSQL fixture from T06. Missing
prerequisites must fail the integration CI job, not silently skip tests. Every task
also passes `git diff --check`, relevant Ruff formatting and the applicable checks
from the approved plan.

The T06 harness must support this local-only lifecycle (these paths do not exist yet):

```sh
bash apps/backend/momentum-adk/scripts/test_database.sh start
export MOMENTUM_TEST_ADMIN_URL='postgresql://postgres:local-test-only@127.0.0.1:55449/postgres'
export MOMENTUM_TEST_CONTAINER=momentum-test-db
i test_database_permissions.py
bash apps/backend/momentum-adk/scripts/test_database.sh stop
```

## Package and stable contracts

- [x] **T01 · PR01 — Independent locked package** (depends: none).
  - Files: `P/pyproject.toml`, `P/uv.lock`, `P/app/__init__.py`, `P/tests/conftest.py`, `P/tests/unit/test_packaging.py`.
  - Acceptance: Python 3.12 locked install; own package namespace; no eager cloud/runtime initialization.
  - Verify: `uv sync --project apps/backend/momentum-adk --frozen --python 3.12`; `u test_packaging.py`.

- [x] **T02 · PR01 — Request and ticker contracts** (depends: T01).
  - Files: `P/app/domain/__init__.py`, `P/app/domain/ticker.py`, `P/app/domain/contracts.py`, `P/tests/unit/test_adk_contracts.py`, `P/tests/unit/test_ticker_symbol.py`.
  - Acceptance: preserve typed requests/results; normalize tickers; reject invalid/duplicate analyst selections.
  - Verify: `u test_adk_contracts.py`; `u test_ticker_symbol.py`.

- [x] **T03 · PR01 — Scoped library checks** (depends: T02).
  - Files: `.github/workflows/momentum.yml`, `P/README.md`, `P/justfile`.
  - Acceptance: SHA-pinned actions; frozen install/lint/unit checks; no cloud credentials or premature image publication.
  - Verify: parse workflow YAML and run its application commands locally; run repository PR-policy tests.

- [x] **T04 · PR02 — Complete financial output schemas** (depends: T02).
  - Files: `P/app/domain/analysis.py`, `P/tests/unit/test_analysis_schemas.py`.
  - Acceptance: preserve all source schemas/fields/renderers; typed sections validate; no financial-method change.
  - Verify: `u test_analysis_schemas.py`; compare source inventory and measure the approximately 859-line source port independently.

- [x] **T05 · PR02 — Workflow state and signal parsing** (depends: T04).
  - Files: `P/app/domain/state.py`, `P/app/domain/rating.py`, `P/tests/unit/test_signal_processing.py`.
  - Acceptance: preserve role-state dependencies and rating normalization.
  - Verify: `u test_signal_processing.py`; use a successor PR if T04 plus T05 exceeds 1,000 lines.

Checkpoint A: package/contracts import cleanly; meaningful tests pass; no partial
application is exposed. Measure complete PR diffs before publication.

## Restricted PostgreSQL storage

- [x] **T06 · PR03 — Disposable migration harness** (depends: T01, T03).
  - Files: `P/tests/integration/conftest.py`, `P/scripts/test_database.sh`, `.github/workflows/momentum.yml`, `D/README.md`, `P/tests/unit/test_database_harness.py`.
  - Acceptance: local-only isolated server/database; real shared Liquibase migrations; cleanup and required integration variables documented.
  - Verify: `u test_database_harness.py`; start/stop script works; fixture rejects remote URLs and existing test roles.

- [x] **T07 · PR03 — Schema and runtime login isolation** (depends: T06).
  - Files: `D/momentum-bootstrap.sql`, `D/changelog/momentum/001-schema.sql`, `D/changelog/db.changelog-master.yaml`, `P/tests/integration/test_database_permissions.py`.
  - Acceptance: migrator owns schema; runtime has no ownership/admin/CREATE rights; audit effective PUBLIC/inherited privileges.
  - Verify: `i test_database_permissions.py`; deny cross-schema access, public/temporary writes and runtime DDL.

- [x] **T08 · PR03 — Pinned ADK session schema** (depends: T07).
  - Files: `D/changelog/momentum/002-adk-sessions.sql`, `D/changelog/db.changelog-master.yaml`, `P/tests/integration/test_adk_session_schema.py`, `P/app/infrastructure/session_database.py`.
  - Acceptance: session tables/indexes/version metadata in `momentum`; enumerated session DML only; missing migrations fail safely.
  - Verify: `i test_adk_session_schema.py`; actual session lifecycle works with runtime credentials and no runtime DDL.

- [x] **T09 · PR04 — Result ORM in the isolated schema** (depends: T04, T07).
  - Files: `P/app/infrastructure/__init__.py`, `P/app/infrastructure/models.py`, `P/tests/unit/test_result_models.py`.
  - Acceptance: preserve financial columns/relationships; explicit schema; session/invocation correlation without ticker/date uniqueness.
  - Verify: `u test_result_models.py`; compare source result-column inventory.

- [x] **T09a — Dedicated session/result databases** (user amendment, depends: T09).
  - Implement in slices of at most five files: explicit Liquibase roots, restricted
    database bootstrap, separate local fixture, and cross-database denial tests.
  - Acceptance: `momentum_sessions` and `momentum_results` share the server, each
    with its own runtime role; defaultdb/Scanner and applied checksums are unchanged.
  - Live cutover, credential distribution and legacy cleanup are separate evidence.

- [x] **T10 · PR05 — Business result migrations** (depends: T08, T09).
  - Files: `D/changelog/momentum-results/001-initial.sql`, `D/changelog/momentum-results.yaml`, `P/tests/integration/test_result_migrations.py`, `P/tests/integration/conftest.py`, `tasks/todo.md`.
  - Acceptance: schema matches ORM; migrations repeat safely; rollback leaves Scanner objects/data/checksums intact.
  - Verify: `i test_result_migrations.py`; rerun affected Scanner shared-database integration checks.

- [x] **T11 · PR06 — Transactional financial section writers** (depends: T09, T10).
  - Files: `P/app/infrastructure/result_writer.py`, `P/app/infrastructure/result_repository.py`, `P/tests/unit/test_result_repository.py`, `P/tests/integration/test_result_persistence.py`.
  - Acceptance: every financial section/correlation commits together; failed section rolls back; runtime grants suffice.
  - Verify: `u test_result_repository.py`; `i test_result_persistence.py`; independently reread populated sections.

Checkpoint B: real PG proves session lifecycle, result rollback and effective
cross-schema denial. Resolve PUBLIC grants/SDK indexes before deployable composition.

## Exclusive LiteLLM transport

- [ ] **T12 · PR07 — Gateway-only model configuration** (depends: T01).
  - Files: `P/app/config/__init__.py`, `P/app/config/settings.py`, `P/app/config/llm.py`, `P/tests/unit/test_gateway_configuration.py`.
  - Acceptance: quick/deep model objects use gateway exclusively; missing URL/key fails; no direct Gemini/Vertex fallback or secret-bearing errors.
  - Verify: `u test_gateway_configuration.py`; reject missing/invalid gateway configuration and redirects.

- [ ] **T13 · PR07 — Native transport against controlled HTTP responses** (depends: T12).
  - Files: `P/tests/integration/test_gateway_transport.py`, `P/tests/integration/gateway_server.py`, `P/tests/unit/test_gateway_errors.py`.
  - Acceptance: actual GenAI serialization; structured/streaming and failure cases; every request targets configured gateway.
  - Verify: `u test_gateway_errors.py`; `i test_gateway_transport.py`; label local HTTP simulation separately from live inference.

Checkpoint C: missing config, timeout, denied key/model and malformed output never
cause direct provider requests. Keep the existing native Gemini API shape.

## Existing market-data and memory behavior

- [ ] **T14 · PR08 — Storage and vendor configuration** (depends: T02).
  - Files: `P/app/config/storage.py`, `P/app/infrastructure/market_data/__init__.py`, `P/app/infrastructure/market_data/configuration.py`, `P/tests/unit/test_storage_configuration.py`.
  - Acceptance: writable non-root paths; preserve vendor defaults; Cloud Run local memory/cache explicitly ephemeral.
  - Verify: `u test_storage_configuration.py` with temporary home/cache paths.

- [ ] **T15 · PR08 — Safe tickers and indicator primitives** (depends: T14).
  - Files: `P/app/infrastructure/market_data/ticker.py`, `P/app/infrastructure/market_data/stockstats.py`, `P/tests/unit/test_safe_ticker_component.py`, `P/tests/unit/test_indicators.py`.
  - Acceptance: safe ticker handling and preserved indicator outputs; deterministic historical input without external calls.
  - Verify: `u test_safe_ticker_component.py`; `u test_indicators.py`.

- [ ] **T16 · PR09 — Alpha Vantage price/indicator adapters** (depends: T15).
  - Files: `P/app/infrastructure/market_data/alpha_vantage/common.py`, `P/app/infrastructure/market_data/alpha_vantage/stock.py`, `P/app/infrastructure/market_data/alpha_vantage/indicator.py`, `P/tests/unit/test_alpha_vantage_prices.py`.
  - Acceptance: preserve request/response shapes; date validation; bounded/sanitized failures and rate limits.
  - Verify: `u test_alpha_vantage_prices.py` with controlled provider responses.

- [ ] **T17 · PR09 — Alpha Vantage report exports** (depends: T16).
  - Files: `P/app/infrastructure/market_data/alpha_vantage/news.py`, `P/app/infrastructure/market_data/alpha_vantage/fundamentals.py`, `P/app/infrastructure/market_data/alpha_vantage/__init__.py`, `P/tests/unit/test_alpha_vantage_reports.py`.
  - Acceptance: preserve available news/fundamental reports and exports; no test provider credentials or live calls.
  - Verify: `u test_alpha_vantage_reports.py`; split PR09 further if adapters plus tests exceed policy.

- [ ] **T18 · PR10 — Yahoo financial reports** (depends: T15).
  - Files: `P/app/infrastructure/market_data/yahoo/__init__.py`, `P/app/infrastructure/market_data/yahoo/finance.py`, `P/tests/unit/test_yahoo_finance.py`.
  - Acceptance: preserve OHLCV/fundamental/indicator shape; deterministic data/dates; bounded failures.
  - Verify: `u test_yahoo_finance.py` with controlled provider responses.

- [ ] **T19 · PR10 — Yahoo news reports** (depends: T18).
  - Files: `P/app/infrastructure/market_data/yahoo/news.py`, `P/tests/unit/test_yahoo_news.py`.
  - Acceptance: preserve ticker/global news formats; handle unavailable sources; sanitize upstream errors.
  - Verify: `u test_yahoo_news.py`; measure complete PR10 diff.

- [ ] **T20 · PR11 — Vendor routing and ADK tools** (depends: T17, T19).
  - Files: `P/app/infrastructure/market_data/router.py`, `P/app/components/tools/__init__.py`, `P/app/components/tools/market_data.py`, `P/tests/unit/test_market_data_tools.py`.
  - Acceptance: preserve selection/tools; optional Scanner enrichment disabled; failures cannot select arbitrary endpoints.
  - Verify: `u test_market_data_tools.py`; local HTTP simulations at actual HTTP integration boundaries.

- [ ] **T21 · PR12 — Decision memory log** (depends: T05, T14).
  - Files: `P/app/infrastructure/memory/__init__.py`, `P/app/infrastructure/memory/log.py`, `P/tests/unit/test_memory_log.py`.
  - Acceptance: preserve decision/reflection behavior; temporary test paths; no durable cross-execution learning claim.
  - Verify: `u test_memory_log.py` with temporary filesystem fixtures.

- [ ] **T22 · PR12 — Execution-memory enrichment** (depends: T20, T21).
  - Files: `P/app/services/__init__.py`, `P/app/services/memory.py`, `P/app/services/execution.py`, `P/tests/unit/test_adk_memory.py`, `P/tests/unit/test_adk_direct_execution.py`.
  - Acceptance: preserve context/outcomes/statistics; forward explicit resume invocation.
  - Verify: `u test_adk_memory.py`; `u test_adk_direct_execution.py`.

Checkpoint D: tool/schema/memory regressions pass. No unavailable tool/report is
replaced with a constant answer or silently removed.

## Original ADK graph and worker

- [ ] **T23 · PR13 — Agent prompts and package boundaries** (depends: T04, T20).
  - Files: `P/app/components/__init__.py`, `P/app/components/agents/__init__.py`, `P/app/components/agents/momentum/__init__.py`, `P/app/components/agents/momentum/prompts.py`, `P/tests/unit/test_agent_prompts.py`.
  - Acceptance: preserve analyst/debate/manager/reflection instructions; no premature root-agent import.
  - Verify: `u test_agent_prompts.py`; compare source role/instruction inventory.

- [ ] **T24 · PR13 — Gateway injection for every agent role** (depends: T05, T13, T23).
  - Files: `P/app/components/agents/momentum/catalog.py`, `P/app/components/callbacks/__init__.py`, `P/app/components/callbacks/statistics.py`, `P/tests/unit/test_structured_agents.py`, `P/tests/unit/test_adk_statistics.py`.
  - Acceptance: collectors/analysts/managers/reflections use LiteLLM; preserve schemas/statistics.
  - Verify: `u test_structured_agents.py`; `u test_adk_statistics.py`; inspect actual model destinations for every role.

- [ ] **T25 · PR14 — Analyst and debate subgraphs** (depends: T22, T24).
  - Files: `P/app/components/agents/momentum/workflow/analysts.py`, `P/app/components/agents/momentum/workflow/debates.py`, `P/app/components/agents/momentum/workflow/results.py`, `P/tests/unit/test_workflow_subgraphs.py`.
  - Acceptance: source analyst order, debate rounds and typed aggregation preserved.
  - Verify: `u test_workflow_subgraphs.py` with controlled ADK events/results.

- [ ] **T26 · PR14 — Original native workflow graph** (depends: T25).
  - Files: `P/app/components/agents/momentum/workflow/__init__.py`, `P/app/components/agents/momentum/workflow/nodes.py`, `P/app/components/agents/momentum/workflow/factory.py`, `P/tests/unit/test_adk_workflow.py`.
  - Acceptance: every original stage present; preserve input/output contracts; no simplified substitute.
  - Verify: `u test_adk_workflow.py`; compare source stages/edges.

- [ ] **T27 · PR14 — Durable execution and resume** (depends: T08, T13, T26).
  - Files: `P/app/services/runtime.py`, `P/tests/unit/test_adk_runtime.py`, `P/tests/unit/test_adk_engine.py`, `P/tests/integration/test_workflow_sessions.py`.
  - Acceptance: explicit separate PG URLs and runtime roles; valid terminal output; session events/resume without DDL.
  - Verify: `u test_adk_runtime.py`; `u test_adk_engine.py`; `i test_workflow_sessions.py`; split PR14 if required.

- [ ] **T28 · PR15 — Bounded database connections** (depends: T11, T12, T27).
  - Files: `P/app/infrastructure/database.py`, `P/app/infrastructure/session_database.py`, `P/tests/integration/test_database_pools.py`.
  - Acceptance: two size-one pools/no overflow, deadlines/disposal; TLS/CA preserved; no automatic second database derivation.
  - Verify: `i test_database_pools.py`; contention times out without connection growth or credential disclosure.

- [ ] **T29 · PR15 — Complete worker command** (depends: T22, T27, T28).
  - Files: `P/app/application.py`, `P/app/job_runner.py`, `P/tests/unit/test_adk_job_runner.py`, `P/tests/integration/test_worker_execution.py`.
  - Acceptance: validate payload; execute full graph; commit result sections/correlation before successful exit.
  - Verify: `u test_adk_job_runner.py`; `i test_worker_execution.py`; missing payload/model/DB/output failures exit nonzero.

- [ ] **T30 · PR15 — Operator and ADK discovery entrypoints** (depends: T29).
  - Files: `P/app/cli.py`, `P/app/agent.py`, `P/app/components/agents/root/__init__.py`, `P/app/components/agents/root/agent.py`, `P/tests/unit/test_cloud_run_entrypoint.py`.
  - Acceptance: installed CLI/native graph discovery works; no HTTP self-invocation or SQL queue.
  - Verify: `u test_cloud_run_entrypoint.py`; `uv run --project apps/backend/momentum-adk --frozen momentum-adk --help`.

Checkpoint E: controlled full-graph execution writes all sections/session correlation;
independent database reads verify them. Failures roll back/exit nonzero. This is not
live model-quality proof; do not publish an image before the complete worker works.

## Private dispatch and production packaging

- [ ] **T31 · PR16 — Scoped execution dispatch** (depends: T02, T29).
  - Files: `P/app/dispatch.py`, `P/tests/unit/test_dispatch.py`, `P/pyproject.toml`, `P/uv.lock`.
  - Acceptance: configured job/container only; analysis payload override only; sanitized failure, no disabled-dispatch success.
  - Verify: `u test_dispatch.py`; verify request/operation parsing against the official Cloud Run API.

- [ ] **T32 · PR16 — Minimal private HTTP contract** (depends: T31).
  - Files: `P/app/main.py`, `P/tests/unit/test_dispatch_api.py`, `P/tests/unit/test_openapi_contract.py`, `P/README.md`.
  - Acceptance: health/submit only; 422/503/502/202 cases; response identifies operation, never claims completed analysis.
  - Verify: `u test_dispatch_api.py`; `u test_openapi_contract.py`; OpenAPI agrees with maintained examples.

- [ ] **T33 · PR17 — Production image boot** (depends: T30, T32).
  - Files: `P/Dockerfile`, `P/.dockerignore`, `P/scripts/container_smoke.py`, `P/tests/unit/test_container_smoke.py`.
  - Acceptance: digest-pinned/non-root Linux image; packaged resources present; real dispatcher boot and invalid worker failure without cloud.
  - Verify: `u test_container_smoke.py`; `docker build --platform linux/amd64 -t momentum:verify apps/backend/momentum-adk`; run image smoke.

- [ ] **T34 · PR17 — Complete application/security CI** (depends: T33).
  - Files: `.github/workflows/momentum.yml`, `.github/dependabot.yml`, `P/justfile`.
  - Acceptance: full unit/real-PG/gateway/image checks and runtime audit; frozen lock/SHA-pinned actions; no cloud credentials/publication in PR jobs.
  - Verify: run workflow commands locally where supported and obtain exact-head CI with no integration skips.

## Dedicated Terraform and release

- [ ] **T35 · PR18 — Isolated Terraform root** (depends: T34).
  - Files: `F/providers.tf`, `F/backend.tf`, `F/variables.tf`, `F/.terraform.lock.hcl`, `F/README.md`.
  - Acceptance: own GCS state prefix; validated inputs/aligned provider constraint; no secrets or state tracked.
  - Verify: locked offline init/validate/format; verify ignored state/local inputs and tracked provider lock.

- [ ] **T36 · PR18 — Dedicated job and worker identity** (depends: T35).
  - Files: `F/job.tf`, `F/iam.tf`, `F/outputs.tf`, `F/tests/job.tftest.hcl`.
  - Acceptance: pinned image/secrets; worker/network explicit; one task/no retries/bounds; required secret grants only.
  - Verify: `terraform -chdir=infra/momentum test`; reject mutable references, public access and broad IAM.

- [ ] **T37 · PR19 — Private dispatcher and job execution grant** (depends: T36).
  - Files: `F/service.tf`, `F/iam.tf`, `F/tests/service.tftest.hcl`, `F/outputs.tf`.
  - Acceptance: explicit invokers/scale-to-zero/bounds; job-scoped overrides permission; no worker secrets on dispatcher.
  - Verify: mocked IAM/service tests including `run.jobs.runWithOverrides`; no anonymous service grant.

- [ ] **T38 · PR19 — Release checks and independent result verifier** (depends: T34, T37).
  - Files: `.github/workflows/momentum.yml`, `.github/dependabot.yml`, `F/README.md`, `P/README.md`, `P/scripts/verify_result.py`.
  - Acceptance: opt-in main-only WIF image publication after checks; record digest/SHA; verifier checks correlation/sections without logging raw records or secrets.
  - Verify: affected checks/workflow parsing; test verifier on disposable persisted result; record published digest separately from apply.

Checkpoint F: final application/image/infra checks pass at exact commits and every
PR satisfies trusted policy. No auto-merge/apply is implied; rebase dependent PRs
as bases land. No live success claim follows from green mock tests or publication.

## Final live evidence

- [ ] **T39 · Rollout — Reviewable deployment** (depends: T38 and real environment prerequisites).
  - Files: `F/README.md` only if operational documentation changes; release inputs/plans remain untracked.
  - Acceptance: correct existing PG database/effective grants/TLS; dedicated gateway key; exact tested digest and reviewed resource diff.
  - Verify: inspect Terraform plan for unintended/destructive/shared changes; never log secrets or commit plans/state.

- [ ] **T40 · Rollout — Completed analysis and isolation proof** (depends: T39 and concrete rollout authorization where required).
  - Files: `F/README.md` only for public-safe verification/limitations.
  - Acceptance: anonymous denial and allowed dispatch; successful job; independent read proves full result/session correlation in `momentum`.
  - Verify: record source SHA/digest, operation/execution, result-verifier success, gateway routing and unaffected Scanner behavior.

Keep publication, apply, job completion, persisted result and model quality as
separate claims. Missing live prerequisites stay pending. Complete the goal only
when every spec criterion has current authoritative proof. Consultation and public
MCP remain later work; they cannot substitute for the complete analysis worker.

## Execution evidence

- T01: `9ac49e0` — frozen Python 3.12 install, three packaging tests, wheel
  build and independent installed-wheel import without runtime configuration.
- T02: `5c2ce7f` — original request/ticker cases retained; invalid inputs and JSON
  roundtrips covered. Full local library suite: 32 passed, no skips.
- T03: `090d3d7` — scoped CI, README and just recipes; Ruff lint/format, workflow
  YAML/SHA pins/shell syntax, local links and 20 repository PR-policy tests pass.
- No worker, image, database migration or live analysis exists at this checkpoint.

- T04: `3e0b1e9` / PR #57 — all 16 source financial JSON schemas and 12 renderer
  ASTs compared: identical. Library suite: 49 passed; lint/format pass.
- T05: `0547249` — workflow states/rating parser byte-identical to reviewed source; original
  signal cases and typed end-to-end state serialization pass: 64 unit cases total.
- PR #56 and #57: library, component scope, size and GitGuardian checks passed.
  Checkpoint A is complete; T06 starts disposable PostgreSQL verification.

- T06: `9d37350`, `477864f` — labeled local-only PostgreSQL, real Liquibase,
  failure cleanup and rejection of existing roles/DSN host overrides verified.
- T07: `45432c1`, `e0c2764` — schema ownership and effective privileges verified;
  PUBLIC TEMP correction preserves existing logins and denies the new worker.
- T08: `4200479` — pinned ADK session/event lifecycle works without runtime DDL;
  missing version/index fails safely. Migration repeat/rollback preserves Scanner.
- Validation: 73 unit cases, 20 real PostgreSQL cases and 4 existing Scanner
  shared-database cases passed without skips; Ruff and lock consistency passed.
- Live foundation applied on 2026-10-20 after explicit user authorization and
  administrator access: runtime login, reviewed PUBLIC TEMP correction, schema
  and five ADK session tables. Existing logins retained their effective TEMP rights.
- Live runtime verification: TLS connection, eight expected permission denials,
  ADK session/event persisted and independently reread through the migration role.
  All Momentum objects are migration-owned; runtime has no administrative flags
  or role membership. Original Scanner rows and migration checksum are unchanged.
  Credentials and detailed evidence stay in the ignored local directory.
- At the T08 checkpoint, result models/migrations/writers (T09–T11) were pending.
  No completed live Momentum analysis was claimed.

- T09: completed-result ORM port preserves all 229 source columns and relationships
  across 12 tables. Explicit schema, required session/invocation/user correlation
  and aware UTC defaults added; ticker administration tables remain out of scope.
  Validation: 80 unit cases, Ruff lint/format and wheel build passed.
  At T09, business migrations and transactional writers were pending (T10–T11).

- User amendment (2026-10-20): separate Momentum sessions and results into two
  logical databases on the existing service. Scanner remains unchanged. T06–T08
  evidence describes the earlier shared deployment, not the new target topology.

- T09a: separate local databases and restricted logins; dedicated session migration
  root, actual ADK persistence after reconnect, cross-database login denial,
  Scanner read denial, bootstrap target guard and isolated rollback verified.
  Live dedicated-database provisioning/cutover remains pending.

- T10: dedicated result root creates all 12 ORM-compatible tables, with
  INSERT/SELECT-only runtime grants. All 39 PostgreSQL cases pass, including
  cross-database denial, target guards and rollback preserving Scanner/sessions.
  Original shared changesets and their checksums remain unchanged.

- T11 / Checkpoint B: 87 unit and 43 PostgreSQL integration cases passed. All
  financial sections and execution correlation commit together through the
  dedicated result login; mapping, constraint and post-flush failures roll back
  every table. Independent reads verify populated sections, repeated analyses
  and result survival after ADK session deletion in the separate database.
  Preserved source mappings, fixing lost market-cap units and zero-price targets.
  Ruff and wheel build pass. Live dedicated-database cutover remains pending.

- Final user clarification (2026-10-20): one `momentum` database, `_sessions` and
  `_analysis` schemas. Supersedes the two-database amendment above. Cleanup of both
  superseded databases and the legacy `defaultdb.momentum` schema is authorized
  after private backup and verification. Separate runtime roles remain required.

- Unified layout verified live (2026-10-20): `momentum._sessions` has five ADK
  tables and `momentum._analysis` has twelve result tables. A real ADK session/event
  survives reconnect; a synthetic complete financial result committed and was
  independently read across all twelve tables, then removed. Cross-schema reads,
  DDL, TEMP and migration-role assumption are denied to runtime logins.
  Three private PostgreSQL custom-format backups were checked before removing
  `momentum_sessions`, `momentum_results` and the legacy `defaultdb.momentum`
  schema through its Liquibase rollback. Scanner row fingerprints and remaining
  migration checksums are unchanged. Runtime URLs now target `/momentum`.
  Validation: 87 unit cases, 48 local PostgreSQL cases, Ruff and wheel build pass.
  No Cloud Run worker deployment or real financial analysis has occurred.


### Worker deployment follow-up (2026-10-21)

The user authorized Terraform deployment and a real Cloud Run ticker test.
PRs #69–#79 port the gateway, original vendors/tools/memory, agent catalog,
workflow, worker and dedicated Terraform root in separate reviewable slices.
PR #81 fixes the two failures exposed by live execution: shared model pacing
for the existing virtual-key limits, and normalization of optional trader
reasoning before writing the NOT NULL legacy result column.

Current local verification: 136 unit tests and 49 disposable PostgreSQL
integration tests pass; Ruff lint/format pass. The PostgreSQL regression includes
an explicit null trader rationale and independently rereads every result section.
The same writer also flushes the previous real AAPL output against remote
PostgreSQL in a deliberately rolled-back diagnostic transaction.

This is a worker deployment, not completion of every checklist item. The private
HTTP dispatcher, its IAM/invocation checks, broader controlled provider cases and
automated image publication remain outstanding. Existing unchecked items are
not promoted to complete solely because a live worker succeeds.

Live verification completed: Cloud Run execution `momentum-analysis-stwdd` exited
0; independent reads verified one AAPL result, all eleven child-table categories
and 92 correlated ADK events in the dedicated database. See the
[rollout evidence](../infra/momentum/README.md#verified-preprod-execution).
