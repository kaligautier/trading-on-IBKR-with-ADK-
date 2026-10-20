# Tasks: Domain databases, results and ADK sessions

Status: DRAFT — spec and plan approved; task checklist awaiting review.
Sources: [spec](../docs/specs/database-per-application.md), [plan](plan.md).
Branch: `feat/database-per-app-tasks`, based on `feat/database-per-app` at `8b1b9f6`.
Momentum target: database `momentum`, schemas `_sessions`, `_analysis`, `liquibase`.
Leading underscores are literal. Scanner keeps `results` and optional `sessions`.
Review this checklist against that parent, not directly against main. It does not
contain application implementation, a live migration, or passing test claims.

## Execution contract

- Execute dependencies first. Every checkbox stays empty until its evidence exists.
- Paths named below are existing files or concrete proposed deliverables. New
  files/commands are not available until their owning task is implemented.
- File paths in Files fields are repository-relative. Private run files are kept
  in a protected ignored location, not Git; paths below name their logical role.
- At most five files per task and one application component per PR. Start a new
  dependent PR before 1,000 counted lines, even inside one plan phase. Shared
  scripts remain purpose-built for the inventoried two domains, not a migration framework.
- Preserve old changeset bytes and identities. Preserve report-v3 and runtime pool
  limits. No live writes until rehearsal, exact release artifacts and operational
  approval exist. Approved implementation tasks do not approve unreviewed cleanup.
- Every code task requires its focused tests, applicable lint/type checks, clean
  diff, no secrets and review of effective privileges. Required integrations must
  fail when prerequisites are absent, never silently skip.
- Tasks that use Momentum execute in a branch containing the authoritative
  foundation established by T01; do not import its unrelated unfinished features.
- An inventory discrepancy may require a spec update. Resolve it explicitly;
  never narrow completion to exclude real source objects or consumers.

## Verification command vocabulary

From the active worktree root, define these shell helpers. They expand each
Verify field into executable commands; targets marked proposed are added by tasks.
The helpers are documentation, not scripts installed or run by this checklist.

```sh
dbtest() {
  TZ=UTC uv run --project apps/backend/market-scanner-adk --frozen python -m pytest \
    -c database/pytest.ini --confcutdir=database/tests -q "database/tests/$1"
}
scanner_test() {
  (cd apps/backend/market-scanner-adk && TZ=UTC uv run --frozen pytest -q "$@")
}
reader_test() {
  (cd apps/backend/market-scanner-api && TZ=UTC uv run --frozen pytest -q "$@")
}
momentum_test() {
  (cd apps/backend/momentum-adk && TZ=UTC uv run --frozen pytest -q "$@")
}
tfcheck() {
  terraform -chdir="$1" fmt -check &&
  terraform -chdir="$1" init -backend=false -input=false -lockfile=readonly &&
  terraform -chdir="$1" validate && terraform -chdir="$1" test
}
migrate() {
  uv run --project apps/backend/market-scanner-adk --frozen python \
    database/scripts/domain_migration.py "$@"
}
```

`database/pytest.ini` and `database/tests/conftest.py` are proposed in T02/T03.
For integration commands, start the dedicated labeled loopback PostgreSQL using
`bash database/scripts/test_domains.sh start` (T03), then use the protected local
connection configuration it produces. Stop with
`bash database/scripts/test_domains.sh stop`, which verifies ownership labels.
Existing component test environments are initialized with `uv sync --frozen` from
the relevant component directory. T28 orchestrates separate component processes
and fixture environments; do not import multiple packages named `app` into one process.

All `runbook.sh` commands below are proposed in T30, then reviewed with real
resource identities before execution. They accept a protected run configuration;
values shown below are local paths, never credentials. Mutating operations require
manifest identity, prior-phase evidence and explicit action; read-only audit does
not implicitly provision, retry a restore, or deploy. An elapsed wait is not proof
of observation: T33 checks real runtime executions and database state.

## P0/P1 — Inventory and guarded migration primitives

### T01 — Establish authoritative component and deployment baselines
- [ ] Dependencies: none. Scope: shared documentation; DB-01, DB-10.
- Acceptance: source revisions, Momentum dependency/deployment owner, all runtime consumers and existing LiteLLM placement are identified from code plus read-only live metadata; unresolved access is recorded, not assumed.
- Verify: `git worktree list --porcelain`; `git log -1 --format='%H %s'`; inspect deployed revisions/job definitions and redacted connection identity; record exact read commands without secret payloads.
- Files: `docs/migrations/domain-databases/baseline.md`.

### T02 — Define manifest and protected connection inputs
- [ ] Dependencies: T01. Scope: shared tooling; DB-01, DB-08.
- Acceptance: validated source/target service identity, exact table/history allowlists, role map and run digest; reject ambiguity, unsafe permissions and secret-bearing diagnostics.
- Verify: `dbtest unit/test_manifest.py` covers wrong host/database, duplicate/unknown identities, malformed inputs and redaction.
- Files: `database/scripts/domain_manifest.py`, `database/tests/unit/test_manifest.py`, `database/pytest.ini`, `database/config/domain-migration.example.json`.

### T03 — Disposable multi-database harness
- [ ] Dependencies: T02. Scope: shared tests; DB-08.
- Acceptance: loopback-only labeled server, unique source/targets, pinned compatible image and real Liquibase; refuse foreign containers/remote hosts and teardown only fixture-owned resources.
- Verify: `bash database/scripts/test_domains.sh start`; `dbtest unit/test_harness.py`; `dbtest integration/test_harness.py`; `bash database/scripts/test_domains.sh stop`.
- Files: `database/scripts/test_domains.sh`, `database/tests/conftest.py`, `database/tests/unit/test_harness.py`, `database/tests/integration/test_harness.py`.

Checkpoint C1: T01–T03 pass; no inferred live deployment, no production mutations.

### T04 — Read-only catalog and dependency inventory
- [ ] Dependencies: T02, T03. Scope: shared tooling; DB-01, DB-08.
- Acceptance: enumerate objects, extensions/types, cross-schema dependencies, roles/PUBLIC rights, histories, locks and consumers; unknown objects fail classification; never change catalog/data.
- Verify: `dbtest integration/test_inventory.py` includes foreign dependencies, duplicate histories and before/after read-only equality.
- Files: `database/scripts/domain_inventory.py`, `database/tests/integration/test_inventory.py`.

### T05 — Provision explicit domain databases and privileges
- [ ] Dependencies: T04. Scope: shared tooling; DB-02, DB-08.
- Acceptance: create only approved targets; retain admin access; restrict effective CONNECT and database-local settings; safe repeated provisioning, occupied/conflicting targets refused.
- Verify: `dbtest integration/test_provision.py` proves actual connections allowed/denied, inherited grants, unchanged unrelated databases and retries.
- Files: `database/scripts/domain_provision.py`, `database/tests/integration/test_provision.py`.

### T06 — Fence source writers and migration runners
- [ ] Dependencies: T05. Scope: shared tooling; DB-06, DB-08.
- Acceptance: record/restore previous ACLs, deny source reconnects, drain or explicitly terminate enumerated consumers with timeout, reject active/unknown migrators; preserve target access for reused roles.
- Verify: `dbtest integration/test_fence.py` includes active transactions, reconnect attempts, unknown sessions and inverse restoration; no cluster-wide NOLOGIN.
- Files: `database/scripts/domain_fence.py`, `database/tests/integration/test_fence.py`.

Checkpoint C2: inventory/provision/fence tests pass with real roles; no unintended cross-domain access.

### T07 — Consistent protected snapshot and backup
- [ ] Dependencies: T06. Scope: shared tooling; DB-03, DB-07, DB-08.
- Acceptance: enforce fence, client/server compatibility and mapped dependencies; dump data plus exact history subset at one stable snapshot; protected backup and integrity manifest; no credentials in argv/logs.
- Verify: `dbtest integration/test_snapshot.py` includes snapshot coherence, sequence/type preservation, permissions and failure cleanup without deleting backups.
- Files: `database/scripts/domain_snapshot.py`, `database/tests/integration/test_snapshot.py`.

### T08 — Restore into verified empty targets
- [ ] Dependencies: T07. Scope: shared tooling; DB-03, DB-08.
- Acceptance: restore native data/objects with reviewed ownership, distinguish provisioned scaffolding from occupied application namespaces; interrupted restore quarantines target and cannot be promoted or silently retried.
- Verify: `dbtest integration/test_restore.py` includes full restore, conflicts, partial failure and untouched source data.
- Files: `database/scripts/domain_restore.py`, `database/tests/integration/test_restore.py`.

### T09 — Preserve and partition migration history
- [ ] Dependencies: T08. Scope: shared tooling; DB-04, DB-08.
- Acceptance: import every original history column for exact approved tuples, reject unknown/duplicate/mismatched entries, independent lock state and no checksum clearing; one domain cannot inherit the other's history.
- Verify: `dbtest integration/test_history.py` compares exact rows, checks locks and denies promotion of inconsistent history.
- Files: `database/scripts/domain_history.py`, `database/tests/integration/test_history.py`.

Checkpoint C3: copied data/history restores are reproducible and source state is unchanged.

### T10 — Compare full content and structural state
- [ ] Dependencies: T09. Scope: shared tooling; DB-03, DB-08.
- Acceptance: streaming deterministic comparisons preserve JSON/null/binary/decimal/timestamp meaning and duplicates without primary keys; separately verify mapped structure, dependencies, sequences and effective ACLs.
- Verify: `dbtest unit/test_comparison.py`; `dbtest integration/test_comparison.py`, including equal counts with unequal content, changed sequence/constraint and schema mapping.
- Files: `database/scripts/domain_compare.py`, `database/tests/unit/test_comparison.py`, `database/tests/integration/test_comparison.py`.

### T11 — Wire explicit CLI phases and evidence
- [ ] Dependencies: T10. Scope: shared tooling; DB-08, DB-10.
- Acceptance: inventory/provision/fence/snapshot/copy/verify have explicit run identities and phase prerequisites; copy composes backup/restore/history without automatic destructive reset; errors are nonzero/redacted.
- Verify: `migrate --help`; `dbtest integration/test_cli.py` exercises prerequisites, interrupted state, tampered manifest and secret-free diagnostics.
- Files: `database/scripts/domain_migration.py`, `database/tests/integration/test_cli.py`.

### T12 — Produce the reviewed live object manifest
- [ ] Dependencies: T11. Scope: read-only operations; DB-01.
- Acceptance: use T01 consumers and fresh catalog evidence to assign every object/history row to domain and target schema; determine actual persistent Scanner sessions and existing Momentum results; dedicated LiteLLM remains verified in place.
- Verify: `migrate inventory --config /secure/domain-migration.json --output /secure/inventory.json`; review exact mapping and reject unknowns before live copy.
- Files: `docs/migrations/domain-databases/inventory-status.md`; private `/secure/inventory.json`, `/secure/approved-manifest.json`.

Checkpoint C4: T10–T12 pass; only local mutations and read-only live inventory so far.

## P2/P3 — Scanner result write/read paths

### T13 — Scanner-only entry point and reversible relocation
- [ ] Dependencies: T09. Scope: shared database; DB-04, DB-11.
- Acceptance: preserve original include identity/bytes; add results relocation/grants with inverse SQL; reject unexpected dependencies before removing empty legacy schema; source remains untouched.
- Verify: `dbtest integration/test_scanner_migrations.py` uses real validate/update-sql/update, second update no-op, rollback and reapply on fresh/copied histories.
- Files: `database/changelog/db.changelog-scanner.yaml`, `database/changelog/market-scanner/002-results.sql`, `database/tests/integration/test_scanner_migrations.py`.

### T14 — Scanner writer on migrated results
- [ ] Dependencies: T10, T13. Scope: `market-scanner-adk`; DB-03, DB-05.
- Acceptance: explicit results configuration writes through existing persistence code; report/asset/horizon rollback, restart durability and pool bound unchanged; old-schema configuration still works for rollback.
- Verify: `scanner_test src/test/integration/test_domain_database.py src/test/unit/services/test_database.py`; fixture invokes real relocation and protected local harness configuration.
- Files: `apps/backend/market-scanner-adk/src/test/integration/test_domain_database.py`, `apps/backend/market-scanner-adk/src/test/unit/services/test_database.py`, `apps/backend/market-scanner-adk/.env.example`.

### T15 — Reader on migrated results with session denial
- [ ] Dependencies: T14. Scope: `market-scanner-api`; DB-02, DB-05, DB-12.
- Acceptance: unchanged report-v3/auth/pagination via actual migrated tables; API restart still reads stored report; runtime reader cannot read synthetic sessions or write results; no new production session store.
- Verify: `reader_test src/test/integration/test_domain_database.py src/test/unit/test_routes.py`; run reader lint/type checks documented in README.
- Files: `apps/backend/market-scanner-api/src/test/integration/test_domain_database.py`, `apps/backend/market-scanner-api/src/test/unit/test_routes.py`, `apps/backend/market-scanner-api/.env.example`.

Checkpoint C5: Scanner write-to-read path passes across processes; separate writer/reader PRs.

## P4 — Momentum schemas and SDK state

### T16 — Momentum-only chain and session relocation
- [ ] Dependencies: T01, T09. Scope: shared database on authoritative foundation; DB-04, DB-11.
- Acceptance: unchanged original paths/contexts; `_analysis` namespace exists; only known SDK tables move to `_sessions` with preserved metadata and inverse SQL; no accidental result-table move.
- Verify: `dbtest integration/test_momentum_migrations.py` proves fresh/copied histories, no-op second update, rollback/reapply and independence from Scanner history.
- Files: `database/changelog/db.changelog-momentum.yaml`, `database/changelog/momentum/003-session-schema.sql`, `database/tests/integration/test_momentum_migrations.py`.

### T17 — One validated schema setting in the session adapter
- [ ] Dependencies: T16. Scope: `momentum-adk`; DB-02, DB-05.
- Acceptance: inspection and SDK search path use the same validated setting; explicit legacy `momentum`/target `_sessions` selection, no silent fallback; pool=1, overflow=0, runtime DDL denial and metadata checks retained.
- Verify: `momentum_test tests/unit/test_session_database.py tests/integration/test_adk_session_schema.py` using the disposable Momentum fixture.
- Files: `apps/backend/momentum-adk/app/infrastructure/session_database.py`, `apps/backend/momentum-adk/tests/unit/test_session_database.py`, `apps/backend/momentum-adk/tests/integration/conftest.py`, `apps/backend/momentum-adk/tests/integration/test_adk_session_schema.py`.

### T18 — Session lifecycle and result independence
- [ ] Dependencies: T17. Scope: `momentum-adk`; DB-02, DB-05, DB-12.
- Acceptance: SDK create/append/resume/restart/delete in `_sessions`; session/event expiry leaves synthetic `_analysis` result readable by result-only role; no production result model added for testing.
- Verify: `momentum_test tests/integration/test_session_result_isolation.py tests/integration/test_database_permissions.py` includes forbidden SQL under real roles.
- Files: `apps/backend/momentum-adk/tests/integration/test_session_result_isolation.py`, `apps/backend/momentum-adk/tests/integration/test_database_permissions.py`.

Checkpoint C6: real pinned SDK lifecycle and reader isolation pass on relocated schema.

### T19 — Resolve inventoried optional objects
- [ ] Dependencies: T12, T13, T16. Scope: shared database; DB-01, DB-03, DB-11.
- Acceptance: map/copy existing Momentum results to `_analysis` or persistent Scanner sessions to `sessions` if present; if absent, record evidence and add no production tables. If object mapping needs over five files, split this task before implementation.
- Verify: `dbtest integration/test_inventory_mapping.py` compares every inventoried object against target map; live inventory demonstrates absence for any omitted optional object set.
- Files: `database/changelog/momentum/004-existing-results.sql` (conditional), `database/changelog/market-scanner/003-existing-sessions.sql` (conditional), `database/changelog/db.changelog-momentum.yaml`, `database/changelog/db.changelog-scanner.yaml`, `database/tests/integration/test_inventory_mapping.py`.

### T20 — Expose independent migration commands
- [ ] Dependencies: T19. Scope: shared database configuration; DB-04, DB-10.
- Acceptance: domain selection sets exact database, entry point and required Momentum context; no default command can apply both domains; examples preserve TLS and disclose no secrets.
- Verify: `dbtest integration/test_migration_entrypoints.py` runs both selected entry points and checks cross-domain no-op; `docker compose -f database/compose.yaml config --quiet` with disposable environment.
- Files: `database/compose.yaml`, `database/.env.example`, `database/liquibase.properties`, `database/README.md`, `database/tests/integration/test_migration_entrypoints.py`.

## P5 — Release and recovery preparation

### T21 — Scanner writer release settings
- [ ] Dependencies: T14, T20. Scope: shared Terraform; DB-06, DB-10.
- Acceptance: writer service/job select same explicit results schema and pinned connection version; old generation remains selectable for recovery; no production target selected before readiness evidence.
- Verify: `tfcheck infra`; inspect full plan for reviewed image/schema/secret changes, pool/scale limits and unrelated drift; validate candidate tfvars before apply.
- Files: `infra/config/release.local.tfvars.example`, `infra/config/preprod.tfvars`, `infra/tests/runtime.tftest.hcl`.

### T22 — Explicit reader schema deployment setting
- [ ] Dependencies: T15, T20. Scope: shared Terraform; DB-06, DB-10.
- Acceptance: validated variable passes DATABASE_SCHEMA explicitly alongside numeric secret version and immutable image; both old/new selections tested; no rights or pool expansion.
- Verify: `tfcheck infra/reader`; inspect full plan and final environment mapping against writer release manifest.
- Files: `infra/reader/variables.tf`, `infra/reader/main.tf`, `infra/reader/tests/reader.tftest.hcl`, `infra/reader/README.md`.

Checkpoint C7: optional objects resolved, independent migrations and Scanner release settings verified.

### T23 — Resolve and prepare Momentum release edits
- [ ] Dependencies: T01, T18, T19. Scope: discovered deployment owner; DB-06, DB-10.
- Acceptance: identify exact job/service configuration and map database `momentum` version plus `_sessions` schema to T17; no speculative new service. Before editing, record at most five exact owner-repository files and its test command in release-map.md; split if larger.
- Verify: review `docs/migrations/domain-databases/release-map.md`; run the owning deployment's documented validate/test command and inspect full plan; this task cannot pass with an unresolved owner or placeholder command.
- Files: `docs/migrations/domain-databases/release-map.md` initially; up to four concrete deployment/test files identified there before edits.

### T24 — Reversible full-state recovery tooling
- [ ] Dependencies: T10, T11, T19. Scope: shared tooling; DB-07, DB-08.
- Acceptance: under verified fence, back up both generations, reverse-map target full state into verified staging, compare then promote to original schemas; preserve updates/deletes/sequences and reject concurrent source writes.
- Verify: `dbtest integration/test_recovery.py` injects new/updated/deleted rows and interrupted restore/promotion; neither generation can silently reopen on failure.
- Files: `database/scripts/domain_recovery.py`, `database/scripts/domain_migration.py`, `database/tests/integration/test_recovery.py`.

### T25 — Exact cleanup dry-run and guarded apply
- [ ] Dependencies: T12, T24. Scope: shared tooling; DB-08, DB-09.
- Acceptance: generate exact object/history deletion manifest; apply requires matching reviewed digest, backup/observation/runtime evidence, no source consumers and no unknown dependencies; preserve system/unrelated objects without broad CASCADE.
- Verify: `dbtest integration/test_cleanup.py` proves dry-run read-only, stale evidence/refused unknowns and exact final inventory.
- Files: `database/scripts/domain_cleanup.py`, `database/scripts/domain_migration.py`, `database/tests/integration/test_cleanup.py`.

Checkpoint C8: owner-resolved release map, inverse recovery and cleanup failure cases pass locally.

### T26 — Domain rollback rehearsal with runtime revisions
- [ ] Dependencies: T21, T22, T23, T24. Scope: shared rehearsal; DB-05, DB-06, DB-07.
- Acceptance: before-write rollback restores old image/schema/version; after-write rollback preserves exact target changes; one domain's rollback leaves the other and LiteLLM state unchanged.
- Verify: `dbtest integration/test_cutover_recovery.py` drives separate component processes and actual connection identity, not mocked success flags.
- Files: `database/tests/integration/test_cutover_recovery.py`, `database/tests/conftest.py`.

### T27 — Final-layout and retention regression suite
- [ ] Dependencies: T15, T18, T19, T25. Scope: shared verification; DB-02, DB-03, DB-04, DB-09, DB-11, DB-12.
- Acceptance: copied and fresh targets converge; all source mappings and full contents verified; readers denied sessions, deletion preserves results, independent migrations/cleanup retain other-domain data.
- Verify: `dbtest integration/test_acceptance.py` emits per-criterion evidence and fails when any required prerequisite or object mapping is missing.
- Files: `database/tests/integration/test_acceptance.py`.

### T28 — Single complete disposable rehearsal command
- [ ] Dependencies: T26, T27. Scope: shared orchestration; DB-03 through DB-12.
- Acceptance: orchestrate isolated Scanner, reader and Momentum environments, real DB/Liquibase and both rollback paths; no real provider calls; protected artifacts and deterministic labeled teardown on success/failure.
- Verify: `dbtest unit/test_rehearsal.py`; `bash database/scripts/rehearse_domains.sh`; measure copy/compare/recovery duration and peak connections; repeat only to verify a new fix or unresolved failure.
- Files: `database/scripts/rehearse_domains.sh`, `database/scripts/test_domains.sh`, `database/tests/unit/test_rehearsal.py`.

Checkpoint C9: full local rehearsal passes with no required skips; duration and connection budget known.

### T29 — CI and migration documentation
- [ ] Dependencies: T28. Scope: shared CI/docs; DB-10.
- Acceptance: CI runs isolated focused tests plus complete rehearsal without live credentials; documentation states exact prerequisites and distinguishes proposed/local/CI/live results; no secret or dump artifacts published.
- Verify: `git diff --check`; `bash database/scripts/rehearse_domains.sh` in CI; inspect job artifacts and application-component/size policy results on each actual PR before merge.
- Files: `.github/workflows/domain-database.yml`, `database/README.md`, `docs/migrations/domain-databases/operations.md`.

### T30 — Concrete operational runbook and approval dossier
- [ ] Dependencies: T12, T23, T29. Scope: shared operations preparation; DB-01, DB-06, DB-07, DB-10.
- Acceptance: exact consumers, fence commands, selected revisions, immutable images, numeric secrets, Liquibase entry points/contexts, recovery commands and cleanup digest; measured maintenance bound, backup retention and observation duration reviewed before live writes.
- Verify: `bash -n database/scripts/runbook.sh`; `bash database/scripts/runbook.sh validate --config /secure/domain-run.json`; `dbtest unit/test_runbook.py`; every mutating subcommand reviewed with concrete targets, not placeholders.
- Files: `database/scripts/runbook.sh`, `database/tests/unit/test_runbook.py`, `docs/migrations/domain-databases/operations.md`, `docs/migrations/domain-databases/release-map.md`; private `/secure/domain-run.json`.

Checkpoint C10: local/CI evidence and exact live dossier reviewed; record authorization before T31/T32.

## P6/P7 — Live cutover, observation and completion

### T31 — Scanner cutover and immediate proof
- [ ] Dependencies: T30 plus recorded operational approval. Scope: live Scanner domain; DB-03, DB-04, DB-05, DB-06, DB-07.
- Acceptance: fence all Scanner consumers, final snapshot/copy/relocation/equality check, coordinated writer/job/reader release; durable report after restart, correct runtime database/schema and source access denied; failure invokes rehearsed recovery.
- Verify: `bash database/scripts/runbook.sh cutover --domain market_scanner --config /secure/domain-run.json`; `bash database/scripts/runbook.sh verify --domain market_scanner --config /secure/domain-run.json`.
- Files: `docs/migrations/domain-databases/evidence.md`; private run evidence and reviewed release references only.

### T32 — Momentum cutover and immediate proof
- [ ] Dependencies: T31 plus recorded operational approval. Scope: live Momentum domain; DB-03, DB-04, DB-05, DB-06, DB-07.
- Acceptance: independent fenced copy and preserved history, actual SDK append/resume/restart in `_sessions` with pool=1, business results in `_analysis` if present; failures do not revert Scanner or disturb LiteLLM.
- Verify: `bash database/scripts/runbook.sh cutover --domain momentum --config /secure/domain-run.json`; `bash database/scripts/runbook.sh verify --domain momentum --config /secure/domain-run.json`.
- Files: `docs/migrations/domain-databases/evidence.md`; private run evidence and reviewed release references only.

### T33 — Observe real runtime behavior for the agreed period
- [ ] Dependencies: T32. Scope: read-only observation plus approved scheduled/synthetic operations; DB-05, DB-06, DB-09.
- Acceptance: minimum 24 hours per domain unless explicitly revised; successful scheduled Scanner result visible via reader, Momentum session round trip, acceptable connections and zero old consumers; elapsed time alone does not pass.
- Verify: `bash database/scripts/runbook.sh observe --config /secure/domain-run.json` queries current jobs/revisions/database activity and timestamps; use bounded polling of identified real executions.
- Files: `docs/migrations/domain-databases/evidence.md`.

Checkpoint C11: both domains satisfy observation; restore-tested retained backups and exact cleanup diff reviewed.

### T34 — Reviewed source cleanup
- [ ] Dependencies: T33 plus approval of concrete destructive diff. Scope: live defaultdb; DB-09, DB-11.
- Acceptance: remove only migrated application objects/history after rechecking backup/evidence/consumer absence; unknown dependencies stop action; managed-service/system objects and unrelated data remain.
- Verify: `bash database/scripts/runbook.sh cleanup-preview --config /secure/domain-run.json`; after approval, `bash database/scripts/runbook.sh cleanup --config /secure/domain-run.json`; fresh inventory proves exact removals.
- Files: `docs/migrations/domain-databases/evidence.md`; private reviewed cleanup manifest and recovery artifacts.

### T35 — Audit every criterion and finalize documentation
- [ ] Dependencies: T34. Scope: read-only verification/docs; DB-01 through DB-12.
- Acceptance: each criterion links direct local/CI/live evidence at the required scope; defaultdb has no application data, final releases use target layout and rollback artifacts are retained; unresolved items keep the goal incomplete.
- Verify: `bash database/scripts/runbook.sh audit --config /secure/domain-run.json`; `git diff --check`; inspect per-criterion evidence and final live state; mark only actually completed tasks.
- Files: `docs/migrations/domain-databases/evidence.md`, `database/README.md`, `tasks/plan.md`, `tasks/todo.md`.

## Scope and delivery checks

- T01–T12: shared foundation, split into independently reviewable PRs as size requires.
- T13/T16/T19/T20: shared migration chains, coordinated sequential edits.
- T14: Scanner writer only; T15: reader only; T17/T18: Momentum only.
- T21–T30: shared release/recovery/CI; T23 owner-specific edits resolved first.
- T31–T35: reviewed live operations and evidence, not implicit effects of merge.
- C1–C11 are evidence checkpoints. Human approval is required at the current task
  gate and at concrete live/destructive execution gates; successful routine local
  checks do not create additional permission prompts.
- No complete task list can authorize guessed live resource names. T01/T12/T23/T30
  make those operations concrete before they can run, with all dependencies kept.

Next gate: validate this checklist to start T01. No application code or live
migration has been performed by this documentation change.
