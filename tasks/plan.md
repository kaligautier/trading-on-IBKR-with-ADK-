# Plan: Domain databases with results and ADK sessions

Status: APPROVED — user answered "go" after reviewing the technical plan.
Specification: [database per domain](../docs/specs/database-per-application.md).
Scope: implement and prove DB-01 through DB-12, including live cutover and cleanup.
This document is a plan, not evidence that any migration has run.

## Decisions and repository evidence

- Keep the existing Aiven service. Create `market_scanner` and `momentum` databases
  with Scanner `results` and optional `sessions`, Momentum `_analysis` and
  `_sessions`, and one `liquibase` schema in each database. Momentum schema names
  include their leading underscores, as explicitly requested by the user.
  Verify existing `litellm` storage without restructuring it.
- Both Scanner runtimes already accept `DATABASE_SCHEMA`; the writer qualifies
  insert targets, and the reader has its own schema setting. Reuse these settings.
  Root Terraform already passes a `database_schema` variable to Scanner; the
  reader Terraform root needs an explicit schema setting for reproducible cutover.
- Preserve applied SQL and `(id, author, filename)` identities. Add domain-specific
  entry points beside the existing master so relative include paths stay stable.
  Each includes its original domain changesets then new relocations. Explicitly
  pass the existing Momentum context when that domain is selected.
- Move the three named Scanner tables into `results` and the enumerated Momentum
  SDK tables into `_sessions` with new transactional changesets. Do not rename the
  entire Momentum schema: it may contain business objects as well. Move other
  objects only when the inventory allowlist proves their ownership.
- Runtime roles remain non-owner roles. Retain workload-specific DML privileges;
  verify namespace permissions and effective ACLs. Only migrators administer
  `liquibase`; reader roles cannot inspect sessions. No runtime DDL privileges.
- Restore original schemas/history into empty targets, relocate there, verify,
  then switch runtimes. Source schemas stay unchanged for recovery. Fresh installs
  follow the same migration chain and must converge on the same final layout.
- The inspected Momentum foundation is `feat/momentum-database-foundation` at
  `19641ad`, separate from this branch. Its docs report a previous live deployment;
  revalidate it. Its adapter hardcodes `momentum` in inspection and search path,
  with one pooled session connection. No Momentum Terraform runtime root exists
  in that inspected foundation. Identify the actual deployment owner before
  defining release edits; do not create an entire new Momentum service here.
- Follow [contribution rules](../CONTRIBUTING.md): one application component per
  PR, at most 1,000 counted lines, generated lockfiles excluded. Shared database
  tooling may accompany one component; split further when its size requires it.

## Dependency graph and delivery boundaries

```text
P0 baseline + inventory contract
 └─ P1 guarded provisioning/copy/verification foundation
     ├─ P2 Scanner database + writer proof
     │   └─ P3 Scanner reader proof
     └─ P4 Momentum database + session proof
          (requires authoritative Momentum foundation)
P2 + P3 + P4 → P5 release configuration + recovery rehearsal
P5 + operational review → P6 live per-domain cutovers
P6 + observation evidence → P7 source cleanup + final audit
```

These delivery slices are broken into tasks of roughly five files or fewer, with
commands, dependencies and acceptance checks in [the checklist](todo.md).
The checklist is awaiting its own review. Split P1 into inventory,
provisioning, copying and verification PRs as needed. Scanner writer, reader and
Momentum changes are separate PRs. Independent code slices may run concurrently
after interfaces are fixed; shared changelog edits, migrations and cutovers are
serialized. This does not authorize parallel mutation of live data.

## P0 — Establish baseline and manifest

Record actual component revisions and the merge dependency on Momentum foundation.
Preserve existing worktrees. Inventory deployed images, jobs, schedules, manual
consumers, database identity, PostgreSQL major version, roles, inherited rights,
extensions, types, sequences, object owners and cross-schema dependencies.

Define a protected manifest with source/target identity, exact object mapping,
changeset allowlists, permitted roles, counts and old/new release references.
Credentials stay in protected external files or Secret Manager; Git evidence
contains neither secrets nor application data. Require the expected service/host
and distinct approved source/target database names.

Unknown objects, ambiguous histories or an unidentified Momentum consumer block
that domain's cutover, not unrelated local development. Resolve them before copy.
Existing dedicated LiteLLM storage is verification-only; a different live layout
requires a concrete spec amendment before copying.

Checkpoint: every object and consumer has a mapping; tooling rejects wrong
identity and unsafe credential files without exposing values (DB-01, DB-08).

## P1 — Reproducible provisioning, copy and comparison

Implement repository-owned tooling in `database/scripts/` with focused tests in
`database/tests/`; reuse the existing Python environment and pinned database image.
Separate read-only inventory/verify from explicit mutations. Bind each action to
a run ID, manifest digest and expected source/target. A lock file is not proof
that an interrupted migration completed.

Provision databases separately from transactional schema DDL. Reconcile explicit
CONNECT grants, PUBLIC rights and database-local role settings, preserving approved
administrator access. Do not blindly reuse global role changes that affect other
databases. Refuse conflicting targets. Retrying provisioning must check complete
state; a partially restored database cannot be accepted as ready.

Use PostgreSQL native dump/restore, selecting exact schemas and dependencies,
instead of reserializing application models. Preserve ownership through reviewed
migrator roles and explicit ACL application. Export the exact Liquibase subset
with all columns intact using the same stable source snapshot. Import only that
subset; initialize independent unlocked lock tables after proving no active
migration. No checksum clearing or unconditional baseline marking.

Final copy requires all writers fenced. Use a client compatible with the source
PostgreSQL version and restore-test an immutable backup. Failed restores quarantine
the target. Recovery uses a newly verified empty target or an explicit reset of
only objects recorded as created by the run; no silent overwrite or broad cascade.

Compare every mapped table using streaming deterministic content digests and
counts. Preserve nulls, binary/JSON values, numeric precision and timestamp
semantics; sort by an unambiguous key or full canonical row, including tables
without primary keys. Check constraints, indexes, sequence state, ownership and
effective ACLs separately. Counts alone cannot release a target.

Checkpoint: disposable tests prove restore, content mismatch detection, partial
failure, retry refusal and credential redaction (DB-02/03/08).

## P2 — Scanner write path in the new database

Add a Scanner-only entry point and new reversible relocation changeset. Create
`results`; move the three allowlisted tables and dependent objects; apply schema
privileges; remove the empty legacy schema only after dependency checks. Rollback
moves objects back and restores original target grants/settings. Do not edit
`market-scanner/001-initial.sql` or report-v3 payloads.

Test fresh-install and copied-history paths through real Liquibase. Select
`DATABASE_SCHEMA=results` in integration fixtures. Preserve atomic report writes,
rollback on failed asset writes and existing pool limits. Keep explicit old-schema
configuration for staged rollout/recovery; final release selects the new layout.

Checkpoint: content equality, second update no-op, writer DDL/metadata access
denied, durable report after restart, and source usable by old code (DB-03/04/05/11).

## P3 — Scanner read path and session isolation

In a separate reader PR, reuse `DATABASE_SCHEMA`, report-v3 schema and existing
repository/route tests. Set `results` explicitly in fixtures and release config.
Preserve authentication, pagination, empty/error behavior and exact payloads.
No new endpoints or public contract changes.

Use real migrated fixtures, not only tables created directly in their final form.
Check effective privileges and attempted queries under the actual reader role.
If Scanner sessions do not exist, synthetic session tables belong only in tests;
do not add production persistence. Reuse existing API tests; no new Postman
workspace or publishing is needed.

Checkpoint: a persisted report is readable through the restarted API; the same
role cannot access session/state/event tables or write results (DB-02/05/12).

## P4 — Momentum sessions and result separation

Base this slice on the verified foundation or its merged successor. Add a
Momentum-only entry point with unchanged original changesets and explicit context,
then new relocations. Create `_analysis` even if empty; move SDK metadata, states,
sessions and events to `_sessions`. Existing business results need an exact
separately reviewed mapping into `_analysis`.

Make one validated schema setting drive both adapter inspection and SDK search
path. Preserve version checks, `pool_size=1`, `max_overflow=0`, runtime DDL denial
and metadata read-only rights. Support old-schema configuration explicitly for
staged releases; never silently fall back after target validation fails.

Test create/append/resume/restart/delete through the pinned ADK adapter. A synthetic
correlated result must survive session deletion, including event cascades within
`_sessions`. Do not invent production analysis tables to exercise this test.

Checkpoint: old/new configurations, fresh/copied histories, second update no-op,
reverse relocation and independent session expiry pass (DB-02/03/04/05/11/12).

## P5 — Release configuration and recovery rehearsal

Version target schema selection with immutable image digests and numeric secret
versions. Scanner service/job share the root setting; add explicit configuration
to `infra/reader` with Terraform tests. Momentum changes belong to the deployment
owner found in P0. No implicit latest versions, larger pools or weakened TLS.

Rehearse source `defaultdb` and both targets on a disposable server: fence, backup,
copy, relocate, compare, switch, restart, read/write, rollback. Fencing must drain
existing writers and deny reconnects; pausing schedules is insufficient. Do not
use cluster-wide NOLOGIN changes that disable target access for reused roles.

Before new writes, rollback selects old image/schema/secret references and source
access. After new writes, fence again and reverse-copy the full domain application
state into a verified source staging area under the inverse mapping. Validate,
then promote only while consumers remain fenced. This avoids guessing deltas and
must preserve updates, deletions, constraints and sequences. Back up both
generations and rehearse failure during recovery. If lossless post-write recovery
cannot be proven, do not resume target writes.

Checkpoint: reviewable release diffs and rehearsal evidence with measured
copy/verification/recovery durations. Fix maintenance timing, maximum duration
and backup retention before live operations (DB-06/07/10).

## P6 — Reviewed domain cutovers

Cut over Scanner first (writer service, job and reader as a unit), verify, then
Momentum. A failed domain stays fenced or returns to source; it must not undo
another domain's successful migration. Keep LiteLLM available.

For each domain: suspend entry points, drain work, fence source access, verify no
writers/migrators, back up, copy/relocate/compare, deploy reviewed references, then
release target access only. Verify database/schema identity through the runtime,
and durable behavior after restart. Old revisions retain no source access.

Evidence includes actual report/session round trips, numeric secret references,
connection use and no source consumers. A real scheduled Scanner run is required
during observation; local mocks cannot replace it. Failures use rehearsed recovery
without allowing simultaneous writable generations. Logs stay redacted.

Checkpoint: live acceptance plus approved observation (minimum 24 hours per
cutover, including scheduled Scanner and Momentum session checks). Record any
approved window change before execution (DB-05/06/07).

## P7 — Source cleanup and completion audit

Prepare an exact manifest-derived cleanup diff. Verify no old consumers, tested
backup and completed observation. Remove only migrated source application objects
and obsolete history. Unexpected dependencies fail closed; no blind cascade or
removal of `defaultdb`. Keep managed-service objects and agreed recovery material.
Final deployments use only target schemas; retained rollback artifacts may retain
old configuration explicitly.

Audit the final layout, original-history-plus-relocation entries, effective rights
and absence of application data in `defaultdb`. Record local, CI, deployment and
cleanup evidence separately against every criterion. Only this audit establishes
completion; delivering code does not.

## Commands and proposed tooling interface

Existing baseline commands, from repository root:

```sh
git diff --check
docker build -t local/deep-copy-liquibase:5.0.4 database
TZ=UTC uv run --project apps/backend/market-scanner-adk --frozen pytest -c apps/backend/market-scanner-adk/pyproject.toml -q apps/backend/market-scanner-adk/src/test/unit
uv run --project apps/backend/market-scanner-api --frozen pytest -c apps/backend/market-scanner-api/pyproject.toml -q apps/backend/market-scanner-api/src/test/unit
terraform fmt -check -recursive infra
terraform -chdir=infra init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra validate
terraform -chdir=infra test
terraform -chdir=infra/reader init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/reader validate
terraform -chdir=infra/reader test
```

Full integration/lint/type checks use component directories and the existing
[database guide](../database/README.md) and
[reader guide](../apps/backend/market-scanner-api/README.md).
The final checklist must specify one disposable cross-database rehearsal command,
including cleanup that checks container labels and loopback identity.

Proposed CLI contract (not implemented or executable yet):

```sh
uv run --project apps/backend/market-scanner-adk --frozen python database/scripts/domain_migration.py inventory --config /secure/domain-migration.json --output /secure/inventory.json
uv run --project apps/backend/market-scanner-adk --frozen python database/scripts/domain_migration.py provision --config /secure/domain-migration.json --manifest /secure/approved-manifest.json --domain market_scanner
uv run --project apps/backend/market-scanner-adk --frozen python database/scripts/domain_migration.py copy --config /secure/domain-migration.json --manifest /secure/approved-manifest.json --domain market_scanner --run-dir /secure/run-scanner
uv run --project apps/backend/market-scanner-adk --frozen python database/scripts/domain_migration.py verify --config /secure/domain-migration.json --manifest /secure/approved-manifest.json --domain market_scanner --run-dir /secure/run-scanner
```

Config files have restrictive permissions; credentials never appear in arguments
or output. Copy itself checks the write fence and target state. The run directory
contains protected backups/evidence, separate from redacted status. Domain
validate/update-sql/update, fencing, release, inverse recovery and cleanup commands
must be pinned to actual deployments in the runbook before P6; placeholders cannot
authorize execution.

## Risks and controls

| Risk | Control and blocking checkpoint |
| --- | --- |
| Momentum code/deployment diverged | P0 establishes authoritative commit, live consumer and coordination owner. |
| Changeset identity/checksum changes | P2/P4 preserve includes and compare full history on fresh/copied paths. |
| Simultaneous source and target writes | P5 rehearses fencing; P6 verifies active sessions before snapshots. |
| Counts hide content drift | P1 compares content, structure, dependencies and sequence state. |
| Reader leaks session content | P3/P4 attempt forbidden queries, including inherited/PUBLIC rights. |
| Recovery loses new writes | P5 rehearses inverse mapping with updates/deletes before writes resume. |
| Excessive downtime/connections | P5 measures timings and combined pools/rollout budgets. |
| Cleanup destroys unrelated data | P7 uses exact allowlists, dependency checks and restorable backups. |

## Acceptance coverage and next gate

| Criteria | Evidence owner |
| --- | --- |
| DB-01 | P0 live manifest and consumer inventory. |
| DB-02, DB-08 | P1 fail-closed checks, P3/P4 effective privileges, P6 live recheck. |
| DB-03, DB-04 | P1 comparator, P2/P4 migrations, P6 final snapshot verification. |
| DB-05, DB-12 | P2/P3 Scanner and P4 Momentum regression tests, P6 runtime proof. |
| DB-06, DB-07 | P5 release/recovery rehearsal, P6 cutover and observation. |
| DB-09, DB-11 | P7 cleanup and final live inventories. |
| DB-10 | P5 exact runbook/release artifacts, P7 consolidated evidence. |

Next gate: human approval of the [task checklist](todo.md); no implementation has
begun. Previous frontend artifacts
remain in the [archived plan](archive/public-frontend-plan.md) and
[archived checklist](archive/public-frontend-todo.md).
