# Tasks: Rebuild domain storage and persist Scanner sessions

Status: implementation approved by the user's “applique et test en local”.
The local foundation, Scanner and reader are implemented and verified; remote
inventory/reset/deployment remain pending. See
[local evidence](../docs/migrations/domain-databases/local-evidence.md).
[Specification](../docs/specs/database-per-application.md) · [Plan](plan.md).

## Rules and command vocabulary

Both databases use `_sessions`, `_analysis`, `liquibase`. No data/history copying,
legacy fallback, reverse recovery, compatibility views or 24-hour wait. Preserve
LiteLLM, infrastructure and unrelated data. Checkboxes mean verified completion;
none is checked by writing this document. At most five files per task and one
application component per PR; split again before 1,000 counted changed lines.
New paths/commands below are proposed deliverables, not currently runnable tools.

Define helpers from the worktree root; component environments use `uv sync --frozen`:

```sh
dbtest() {
  TZ=UTC uv run --project apps/backend/market-scanner-adk --frozen python -m pytest \
    -c database/pytest.ini --confcutdir=database/tests -q "database/tests/$1"
}
scanner_test() { (cd apps/backend/market-scanner-adk && TZ=UTC uv run --frozen pytest -q "$@"); }
reader_test() { (cd apps/backend/market-scanner-api && TZ=UTC uv run --frozen pytest -q "$@"); }
momentum_test() { (cd apps/backend/momentum-adk && TZ=UTC uv run --frozen pytest -q "$@"); }
tfcheck() {
  terraform -chdir="$1" fmt -check &&
  terraform -chdir="$1" init -backend=false -input=false -lockfile=readonly &&
  terraform -chdir="$1" validate && terraform -chdir="$1" test
}
rebuild() {
  uv run --project apps/backend/market-scanner-adk --frozen python database/scripts/rebuild_domains.py "$@"
}
```

T02 provides a labeled loopback-only disposable PostgreSQL harness. Integrations
require it and fail rather than skip when unavailable. T15 uses separate processes
for packages named `app`. Every code task also runs applicable Ruff/type checks,
checks the diff for secrets, and records actual test output. Live resource names
are resolved in T01/T14/T16; placeholders never authorize guessed operations.

### T01 — Inventory reset scope and deployed consumers
- [ ] Dependencies: none. Scope: shared docs; DB-01.
- Acceptance: exact service identity, domain databases/legacy objects, all consumers, role budgets and authoritative Momentum deployment are recorded; LiteLLM/system/unrelated objects explicitly excluded.
- Verify: read-only catalog and deployment metadata; `git worktree list --porcelain`; record actual commands and unresolved access without secrets.
- Files: `docs/migrations/domain-databases/baseline.md`.

### T02 — Disposable fresh-database harness
- [x] Dependencies: T01. Scope: shared tests; DB-09.
- Acceptance: pinned PostgreSQL/Liquibase, owned labeled containers, loopback-only targets; refuse remote/foreign fixtures; teardown only its own resources.
- Verify: `bash database/scripts/test_domains.sh start`; `dbtest test_harness.py`; `bash database/scripts/test_domains.sh stop`.
- Files: `database/scripts/test_domains.sh`, `database/pytest.ini`, `database/tests/conftest.py`, `database/tests/test_harness.py`.

### T03 — Fresh Scanner analysis and session schema
- [x] Dependencies: T02. Scope: shared database; DB-02.
- Acceptance: final `_analysis` report/asset/horizon model plus `_sessions` pinned-ADK tables, keys/indexes/metadata; independent fresh Liquibase history, no legacy chain or runtime DDL.
- Verify: `dbtest test_scanner_schema.py` runs fresh validate/update/update-sql and a second no-op update, comparing session schema against pinned SDK definitions.
- Files: `database/changelog/db.changelog-scanner.yaml`, `database/changelog/market-scanner/001-initial.sql`, `database/changelog/market-scanner/002-sessions.sql`, `database/tests/test_scanner_schema.py`.

### T04 — Fresh Momentum schema on authoritative foundation
- [ ] Dependencies: T01, T02. Scope: shared database; DB-02, DB-06.
- Acceptance: `_sessions` matches pinned SDK, `_analysis` contains implemented results only, empty namespace otherwise; independent chain, no Scanner changesets.
- Verify: `dbtest test_momentum_schema.py` checks fresh/second update and both domain history isolation; use the foundation revision resolved in T01.
- Files: `database/changelog/db.changelog-momentum.yaml`, `database/changelog/momentum/001-schema.sql`, `database/changelog/momentum/002-adk-sessions.sql`, `database/tests/test_momentum_schema.py`.

Checkpoint C1: fresh schema contracts pass; no application data copied or retained for compatibility.

### T05 — Guarded domain reset and explicit bootstrap CLI
- [ ] Dependencies: T03, T04. Scope: shared operations code; DB-01, DB-09, DB-11.
- Acceptance: inspect/reset/bootstrap/verify are separate explicit actions; validate expected service, protected config and exact object allowlist; reject active unknown consumers, unexpected dependencies and forbidden databases; no automatic reset on retry.
- Verify: `dbtest test_rebuild.py` proves correct erasure, occupied/partial state handling, redaction and refusal to touch LiteLLM/system/unrelated data; `rebuild --help`.
- Files: `database/scripts/rebuild_domains.py`, `database/config/rebuild.example.json`, `database/tests/test_rebuild.py`.

### T06 — Domain-specific grants and connection limits
- [ ] Dependencies: T05. Scope: shared database; DB-03, DB-08.
- Acceptance: runtime writers get session DML plus intended analysis writes, metadata SELECT only; readers get analyses only; no runtime DDL/history access; database CONNECT and role limits include both Scanner pools.
- Verify: `dbtest test_permissions.py` uses actual roles, inherited/PUBLIC grants and concurrent connections; bootstrap repetition never silently restores excess privileges.
- Files: `database/domain-bootstrap.sql`, `database/scripts/rebuild_domains.py`, `database/tests/test_permissions.py`.

### T07 — Scanner PostgreSQL session adapter
- [x] Dependencies: T03, T06. Scope: `market-scanner-adk`; DB-04, DB-08.
- Acceptance: one validated `_sessions` configuration and exact schema preflight before SDK preparation; pool=1/overflow=0, TLS preserved, no in-memory fallback, explicit close on errors.
- Verify: `scanner_test src/test/unit/services/test_session_database.py src/test/integration/test_session_database.py` covers DDL denial, wrong schema, actual session restart and engine disposal.
- Files: `apps/backend/market-scanner-adk/src/app/services/session_database.py`, `apps/backend/market-scanner-adk/src/app/config/settings.py`, `apps/backend/market-scanner-adk/src/test/unit/services/test_session_database.py`, `apps/backend/market-scanner-adk/src/test/integration/test_session_database.py`.

Checkpoint C2: scoped reset/permissions and persistent Scanner adapter work on disposable storage.

### T08 — Persist scheduled Scanner job sessions
- [x] Dependencies: T07. Scope: `market-scanner-adk`; DB-04, DB-07.
- Acceptance: replace InMemorySessionService with shared adapter, retain session/report correlation and close both stores; explicit repeated-ID/completed-run behavior; storage failure prevents success without erasing partial evidence.
- Verify: `scanner_test src/test/unit/test_daily_scan.py src/test/integration/test_daily_scan_sessions.py` covers restart, duplicate execution ID and session/report failures with mocked model/data providers.
- Files: `apps/backend/market-scanner-adk/src/app/jobs/daily_scan.py`, `apps/backend/market-scanner-adk/src/test/unit/test_daily_scan.py`, `apps/backend/market-scanner-adk/src/test/integration/test_daily_scan_sessions.py`.

### T09 — Persist interactive ADK service sessions
- [x] Dependencies: T07. Scope: `market-scanner-adk`; DB-04, DB-08.
- Acceptance: inspect installed get_fast_api_app integration point; wire same PostgreSQL store/schema and lifecycle; preserve authenticated routes and fail closed if storage/schema unavailable.
- Verify: `scanner_test src/test/unit/test_application.py src/test/integration/test_application_sessions.py` creates session/appends event, restarts service and reads persisted state through real authenticated routes.
- Files: `apps/backend/market-scanner-adk/src/app/application.py`, `apps/backend/market-scanner-adk/src/test/unit/test_application.py`, `apps/backend/market-scanner-adk/src/test/integration/test_application_sessions.py`.

### T10 — Scanner analysis persistence and correlation
- [x] Dependencies: T08, T09. Scope: `market-scanner-adk`; DB-05, DB-07.
- Acceptance: `_analysis` is the only production business schema; successful run leaves a report linked unambiguously to durable session, existing report-v3/atomic report writes retained; session deletion preserves analysis.
- Verify: `scanner_test src/test/integration/test_domain_database.py src/test/unit/services/test_market_scan_persistence.py`; validate post-restart report plus session and partial-failure handling.
- Files: `apps/backend/market-scanner-adk/src/app/services/market_scan_persistence.py`, `apps/backend/market-scanner-adk/src/app/config/settings.py`, `apps/backend/market-scanner-adk/src/test/integration/test_domain_database.py`, `apps/backend/market-scanner-adk/src/test/unit/services/test_market_scan_persistence.py`, `apps/backend/market-scanner-adk/.env.example`.

Checkpoint C3: both Scanner entry points persist sessions; new analyses survive restart and session deletion.

### T11 — Reader selects analyses only
- [x] Dependencies: T10. Scope: `market-scanner-api`; DB-03, DB-05.
- Acceptance: `_analysis` default/config, unchanged report-v3/auth/pagination; real reader cannot read sessions/events/state or write analyses; no legacy schema fallback.
- Verify: `reader_test src/test/integration/test_domain_database.py src/test/unit/test_routes.py`; run reader Ruff/mypy and existing route regression suite.
- Files: `apps/backend/market-scanner-api/src/app/config/settings.py`, `apps/backend/market-scanner-api/src/test/integration/test_domain_database.py`, `apps/backend/market-scanner-api/src/test/unit/test_routes.py`, `apps/backend/market-scanner-api/.env.example`.

### T12 — Momentum adapter selects final schemas
- [x] Dependencies: T04, T06. Scope: `momentum-adk`; DB-06, DB-08.
- Acceptance: actual adapter inspection/search path target `_sessions`, pool=1, runtime DDL denied; implemented analysis storage selects `_analysis`; no old-schema mode or new workflow feature.
- Verify: `momentum_test tests/integration/test_adk_session_schema.py tests/integration/test_database_permissions.py`; create/append/restart/delete with actual SDK, no copied history.
- Files: `apps/backend/momentum-adk/app/infrastructure/session_database.py`, `apps/backend/momentum-adk/tests/integration/conftest.py`, `apps/backend/momentum-adk/tests/integration/test_adk_session_schema.py`, `apps/backend/momentum-adk/tests/integration/test_database_permissions.py`; add existing analysis configuration as a fifth file only if T01 proves it exists, otherwise record namespace-only state.

### T13 — Scanner and reader release settings
- [ ] Dependencies: T11. Scope: shared Terraform; DB-08, DB-10.
- Acceptance: explicit final schemas in writer service/job and reader, numeric secret versions and immutable images; budget counts both writer/session pools across replicas/jobs; no TLS weakening.
- Verify: `tfcheck infra`; `tfcheck infra/reader`; full plan contains only reviewed configuration changes and no implied apply to old storage.
- Files: `infra/config/preprod.tfvars`, `infra/market_scanner.tf`, `infra/reader/main.tf`, `infra/tests/runtime.tftest.hcl`, `infra/reader/tests/reader.tftest.hcl`.

### T14 — Resolve exact Momentum deployment changes
- [ ] Dependencies: T01, T12. Scope: actual deployment owner; DB-10.
- Acceptance: exact target image/config/secret mapping recorded; before editing list at most four owner-repository files plus release-map, with its real validation command; no guessed service or unimplemented new runtime.
- Verify: inspect `docs/migrations/domain-databases/release-map.md`, run the recorded owning deployment validation/tests and inspect its full plan; unresolved owner cannot pass.
- Files: `docs/migrations/domain-databases/release-map.md` plus at most four concrete deployment files identified before editing.

Checkpoint C4: both domains and reader use only final schemas; connection budget and deployment owners resolved.

### T15 — Complete fresh rebuild rehearsal
- [ ] Dependencies: T13, T14. Scope: shared tests; DB-02 through DB-11.
- Acceptance: isolated local reset/bootstrap plus separate runtime processes, fresh Scanner session+report, reader restart, Momentum SDK round trip and session deletion isolation; test failures without automatic destructive resets.
- Verify: `bash database/scripts/rehearse_domains.sh`; `dbtest test_acceptance.py`; measure combined connections; required integrations cannot skip.
- Files: `database/scripts/rehearse_domains.sh`, `database/tests/test_acceptance.py`, `database/tests/conftest.py`.

### T16 — CI, fresh migration commands and concrete runbook
- [ ] Dependencies: T15. Scope: shared CI/docs; DB-10, DB-12.
- Acceptance: domain-specific Compose selection never applies both chains; CI runs isolated rehearsal without live secrets; exact stop/reset/bootstrap/deploy/run/verify commands and targets recorded, no legacy-copy steps.
- Verify: `git diff --check`; `bash database/scripts/rehearse_domains.sh` in CI; inspect command syntax and concrete resource identities in runbook before live execution.
- Files: `.github/workflows/domain-database.yml`, `database/compose.yaml`, `database/.env.example`, `database/README.md`, `docs/migrations/domain-databases/operations.md`.

Checkpoint C5: local/CI evidence and exact live commands exist; data loss is already authorized within scope.

### T17 — Remove obsolete shared-database entry points
- [ ] Dependencies: T16. Scope: shared configuration; DB-10.
- Acceptance: supported CLI/Compose/local commands select a fresh domain chain; obsolete shared master and old global bootstrap scripts are removed after checking callers; no documented path creates legacy schemas.
- Verify: `rg -n 'db.changelog-master|momentum-public-privileges|momentum-bootstrap|bootstrap.sql' database apps infra .github` and inspect every remaining reference; rerun `bash database/scripts/rehearse_domains.sh` after removals.
- Files: `database/changelog/db.changelog-master.yaml`, `database/liquibase.properties`, `database/bootstrap.sql`, `database/momentum-bootstrap.sql`, `database/momentum-public-privileges.sql` (remove existing obsolete scripts only).

### T18 — Execute authorized reset and deploy fresh storage
- [ ] Dependencies: T17. Scope: live domain storage; DB-01, DB-02, DB-03, DB-09, DB-10, DB-11.
- Acceptance: stop enumerated old consumers; recheck scope; erase only authorized domain storage/legacy objects; fresh schemas/grants verified before deploying final releases; failure leaves consumers stopped until repaired.
- Verify: execute exact stop/deploy commands from T16; `rebuild inspect --config /secure/domain-rebuild.json`; `rebuild reset --config /secure/domain-rebuild.json`; `rebuild bootstrap --config /secure/domain-rebuild.json`; `rebuild verify --config /secure/domain-rebuild.json`.
- Files: `docs/migrations/domain-databases/evidence.md`; protected live configuration/evidence outside Git. No further data-loss permission prompt unless the actual scope differs.

### T19 — Fresh Scanner run and completion audit
- [ ] Dependencies: T18. Scope: actual runtime verification; DB-01 through DB-12.
- Acceptance: trigger one new Scanner run under the user's rerun instruction; durable ADK state/events and correlated report survive restart and reader fetch; Momentum synthetic round trip succeeds; defaultdb is free of domain data and LiteLLM remains intact.
- Verify: run exact trigger/restart/read commands from T16 with real authenticated consumers; `rebuild verify --config /secure/domain-rebuild.json`; correlate session/report IDs and recorded execution status; HTTP health alone cannot pass.
- Files: `docs/migrations/domain-databases/evidence.md`, `database/README.md`, `tasks/todo.md`, `tasks/plan.md`.

## Current gate

The local apply is approved and underway. Checked items have local evidence;
unchecked combined/live tasks are not passed by local tests. Implemented harness
paths are `database/scripts/local_domains.py` and `rehearse_domains.py`, replacing
the proposed shell harnesses. The local script intentionally cannot reset remote
storage. No data-copy or compatibility machinery has been introduced.
