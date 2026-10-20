# Spec: One PostgreSQL database per domain, separate results and sessions

Status: APPROVED for technical planning — user answered "go" after reviewing the revised spec.
Date: 2026-10-20.
Base: `origin/main` at `9bbf570`; branch: `feat/database-per-app`.

## Objective

Move application data out of Aiven `defaultdb` into one database per business
domain on the existing PostgreSQL service. Within each domain, separate durable
business results from ADK execution state. The domain's agent worker and reader
API share the database with workload-specific permissions. Preserve data,
migration identity, runtime behavior, and the ability to recover. The intended
end state is:

```text
Existing Aiven PostgreSQL service
├── market_scanner
│   ├── results         (reports, assets, horizons)
│   ├── sessions        (only if persistent Scanner sessions exist)
│   └── liquibase       (Scanner migration history)
├── momentum
│   ├── _analysis       (existing business results, if any; future analyses)
│   ├── _sessions       (ADK sessions, events, states and SDK metadata)
│   └── liquibase       (Momentum migration history)
├── litellm             (existing LiteLLM-managed objects and history)
└── defaultdb           (no application data after verified cleanup)
```

This replaces both the shared-`defaultdb` design and the earlier proposal to keep
domain-named schemas inside the new databases. A database is owned by a domain,
not by a deployment: `market-scanner-adk` and `market-scanner-api` do not get
separate databases. Business schemas are independent of ADK implementation details.
The user explicitly selected `_analysis` and `_sessions` for Momentum; these are
literal schema names, including their leading underscores. Scanner uses `results`
and optional `sessions`.
Scanner and Momentum each retain one `liquibase` schema tracking both results
and session migrations. LiteLLM retains its native schema organization.
No new Aiven service, plan upgrade, PostgreSQL upgrade, result-producing feature,
or persistent-session feature is included. Create the Momentum `_analysis`
namespace even if no business result tables exist yet; do not invent those tables.
Scanner `sessions` is required only when inventory establishes persistent storage.
Capacity and connection budgets remain service-wide.
Pricing and current capacity must be checked before provisioning; no cost change
is asserted by this specification.

## Assumptions requiring review

The design is approved. Exact maintenance timing, measured duration and recovery
retention remain operational decisions to record before live execution; spec
approval is not approval of an unreviewed production cutover.

- A bounded maintenance window may pause all affected writers and migrations.
  This is proposed, not yet approved. Zero downtime would require a revised design.
- Existing runtime role names and their intended permissions remain stable.
  Per-domain migrator identities are not required by this migration; the
  existing `database_migrator` may administer both domain databases.
- After cutover, keep the source application objects inaccessible to runtimes
  for a proposed minimum of 24 hours, including one successful scheduled Scanner
  run and one Momentum session round trip. Cleanup follows explicit verification.
- Aiven access, exact deployed revisions, data volume, and all active consumers
  will be inventoried before execution. Repository state alone cannot prove them.

## Verified repository state

| Evidence | Observation and consequence |
| --- | --- |
| [Database bootstrap](../../database/bootstrap.sql) | Uses `current_database()`, shared migrator, and global runtime role settings. Provisioning must target explicit databases and audit effective privileges. |
| [Root changelog](../../database/changelog/db.changelog-master.yaml) | Main includes Scanner only. Separate application entry points must preserve existing changeset identities. |
| [Database example](../../database/.env.example) | JDBC example still targets `defaultdb`. |
| [Scanner job](../../apps/backend/market-scanner-adk/src/app/jobs/daily_scan.py) | Uses `InMemorySessionService`; do not invent persistent sessions to migrate. Inventory other deployed entry points. |
| [Scanner service](../../infra/market_scanner.tf) and [job](../../infra/market_scanner_job.tf) | Both consume `market-scanner-database-url` at `database_secret_version`. Both must switch together. |
| [Reader](../../infra/reader/main.tf) | Uses a separate configurable secret and version; include it in the same Scanner cutover. |
| [LiteLLM Aiven bootstrap](../../infra/litellm/scripts/bootstrap_aiven.py) | Already provisions `litellm`, preserves existing credentials and salt, and configures dedicated access. Verify deployed state before deciding any copy is needed. |

The separate local `feat/momentum-database-foundation` branch at `19641ad`
contains `database/momentum-bootstrap.sql`, `momentum/001-schema.sql`,
`momentum/002-adk-sessions.sql`, and the Momentum session adapter/tests.
It adds Momentum to the shared root changelog with `@momentum` contexts. Its
adapter uses `pool_size=1`, `max_overflow=0`; the role limit is 4, which is a
different constraint. These files are not present on this spec's main base.
The implementation plan must explicitly coordinate with that branch or its
merged successor; do not import unrelated Momentum work or assume it is deployed.

No remote database inventory or data migration has been performed for this spec.

## Required behavior

### Inventory and provisioning

- Produce a redacted manifest of source databases, schemas, tables, extensions,
  sequences, owners, privileges, row counts, migration rows and active consumers.
  Include schedules, running jobs, service revisions, manual entry points and
  administrative migration processes. Record PostgreSQL/client versions.
- Identify cross-schema dependencies, large objects and objects outside selected
  schemas. Unknown dependencies, unmapped application tables or ambiguous session
  ownership stop the operation; a schema-only dump is not a complete inventory.
- Create missing databases on the existing service using versioned provisioning
  code. An existing target must be verified as the exact intended destination;
  conflicting or partially populated targets must fail closed, not be overwritten.
- Restrict effective `CONNECT` privileges to each application's approved roles
  and administrators. Audit `PUBLIC`, role memberships and default privileges.
  Deny runtime creation of schemas/tables and access to other application databases.
  Preserve LiteLLM's required migration privileges inside its own database.
- Apply database-specific search paths and timeouts where appropriate. Preserve
  current pool limits; account for rollout overlap, migrations and administrative
  connections in the shared service budget. Do not increase pools to fix migration.
- Preserve managed-service administration access to `defaultdb`; empty means no
  application objects/data, not removal of system schemas or the database itself.

### Schema responsibilities and access

| Schema | Content | Intended runtime access |
| --- | --- | --- |
| Scanner `results`; Momentum `_analysis` | Domain reports, analyses and their normalized business rows. No SDK state tables. | Domain worker writes with its existing business privileges; domain reader has SELECT only. |
| Scanner `sessions`; Momentum `_sessions` | ADK sessions, events, application/user state and SDK schema metadata. | Session-enabled worker has required session DML; SDK metadata stays read-only. Reader has no access. |
| `liquibase` | One domain-local changelog and lock table covering both schemas. | Migrator only; runtime roles cannot read or change migration metadata. |

- The Scanner reader role must have neither `USAGE` on `sessions` nor rights on
  its tables. Check direct grants, PUBLIC and role inheritance. The same rule
  applies to `_sessions` for any existing Momentum reader; building a new Momentum
  API is out of scope.
- Worker permissions remain workload-specific: a Scanner report writer does not
  gain session DML merely because the schema exists. A worker using both stores
  may access both, but neither runtime role gains ownership or DDL privileges.
- Session retention must not delete business results. Keep correlation identifiers
  such as `session_id`, but require results to remain readable after session expiry.
  No result-to-session cascading deletion or FK that prevents session cleanup.
  This migration does not enable a new purge schedule or choose a retention policy.
- Select the intended schema explicitly in business models/queries and SDK
  connections. Verify the actual ADK schema inspector and session adapter against
  `_sessions` for Momentum (`sessions` for any persistent Scanner consumer);
  changing only the database URL or role search path is insufficient.
- Separate schemas do not imply extra connection pools. Preserve existing pool
  sizing and include any required distinct engine in the service-wide budget.

### Source-to-target mapping

Source locations below describe inspected code and must be confirmed by live
inventory. Preserve table names; only database/schema placement changes.

| Source objects | Target | Required adaptation |
| --- | --- | --- |
| Scanner `market_scanner.market_scans`, `market_scan_assets`, `market_scan_horizons` | Database `market_scanner`, schema `results` | Writer mapping/search path and reader schema setting; preserve report-v3 contract. |
| Momentum `momentum.adk_internal_metadata`, `app_states`, `user_states`, `sessions`, `events` | Database `momentum`, schema `_sessions` | SDK schema inspection and connection settings, indexes, keys and privileges. |
| Any inventoried Momentum business result tables | Database `momentum`, schema `_analysis` | Explicit table/dependency allowlist; do not move them with SDK tables. |
| Any inventoried persistent Scanner session tables | Database `market_scanner`, schema `sessions` | Identify actual owner/consumer first; in-memory sessions require no copy. |
| Shared Liquibase history | Each domain's `liquibase` schema | Preserve original domain subset, then append new schema-relocation changesets. |
| Dedicated LiteLLM objects | Existing `litellm` database and native schemas | Verify existing placement; no normalization to results/sessions. |

Legacy schemas may exist temporarily during target restoration. Final application
objects must live in the target schemas above; no permanent duplicate tables or
compatibility views may leave the old layout authoritative. Inventory all views,
functions and textual SQL references affected by relocation. Compare source and
target structure using this mapping rather than requiring identical schema names.

### Data and Liquibase history

- Back up source data and relevant metadata before mutation. Store dumps and
  manifests outside Git with restricted permissions and restore-test the backup.
- Quiesce affected writers and migration runners before the final snapshot.
  Drain existing sessions and prevent reconnects to old storage. The fence must
  cover already-running jobs, retries and alternate credentials, not only schedules.
- Restore application objects with their types, keys, constraints, indexes,
  sequence states and intended ownership/ACLs. Preserve identifiers, timestamps,
  JSON/session payloads and all existing results. No lossy reserialization.
- Partition `liquibase.databasechangelog` by an explicit reviewed allowlist of
  `(id, author, filename)` for each application. Preserve all original column
  values, including checksum, execution metadata and contexts. Reject unknown or
  duplicate identities; do not classify ownership by a loose name prefix alone.
- Preserve changelog file paths and content, or explicitly retain their original
  logical identities. Each new entry point includes only its application's files.
  A fresh installation and an imported installation must both work.
- Do not edit applied creation changesets to substitute target schema names
  (`results`/`sessions` for Scanner, `_analysis`/`_sessions` for Momentum). Introduce new, reversible domain-local changesets for
  relocation and grants after the original history. Fresh installations run the
  original chain then these changesets; imported installations preserve the
  original subset and execute only the new changesets. Both reach the same layout.
  Rehearse restoration and relocation inside the target database while source
  consumers are fenced; never rename active source schemas as an implicit cutover.
- Create independent Liquibase locking state after proving no migration is active;
  do not copy a held lock. Do not use `clearCheckSums`, blind `changelogSync`, or
  rerun creation changesets to hide inconsistent imported history.
- Already-applied entries must produce no application DDL on `update-sql`;
  only approved new relocation changesets may appear on the first target update.
  A second `update` must be a no-op. Applying or rolling back a new migration in one
  target must not touch another application's objects or migration history.
- Keep LiteLLM's native migration mechanism, history and encryption salt intact.
  If it already uses its dedicated database, validate it without recopying it or
  rotating credentials. If inventory contradicts this, specify its exact source
  mapping and recovery procedure before any copy.

### Configuration and cutover

- Create new connection-secret versions that select the target database and
  retain the required TLS/CA options, runtime identity and connection settings.
  Never print URLs, payloads, passwords, session contents or secret values.
- Record previous and target version references. Select immutable versions in
  Terraform/release configuration; a moving `latest` reference is insufficient
  for a reproducible switch or rollback.
- Switch Scanner writer service, job, reader and any actual persistent-session
  consumer as one application unit. Switch Momentum consumers using their real
  deployment configuration identified during inventory. LiteLLM remains available
  unless its actual storage requires a separately verified cutover.
- Ship matching schema configuration/code with target secret references. Scanner
  reader defaults currently select `market_scanner`; Momentum's inspected adapter
  checks and selects `momentum`. Update those assumptions to `results` and
  `_sessions` respectively, including integration fixtures and schema assertions.
  Staged releases must not send old-layout code to relocated target tables.
- Verify target identity from the actual runtime connection, plus a durable write
  and read after process restart. HTTP health, green CI and a Terraform plan alone
  do not prove successful migration.
- Resume writes only after copied data/history and permissions pass verification.
  Prevent simultaneous writable source and target generations.

### Rollback and cleanup

- Before target writes resume, rollback restores prior secret references and
  revisions with their original schema configuration, removes the source write
  fence and resumes the prior schedules.
  Preserve source data unchanged until this path has been rehearsed.
- Once target writes exist, merely restoring old URLs would lose data. Pause
  writers again, back up the target, reconcile every post-cutover change back to
  source under a tested procedure, validate equality, then switch. If this path
  is not proven, keep writes stopped and repair forward; never claim lossless rollback.
- Reverse reconciliation must apply the inverse table/schema mapping, including
  session updates/deletes and result inserts. A target changeset rollback alone
  does not copy new data back to the original database.
- Cleanup is a separate reviewed operation after the observation window, successful
  runtime checks, zero old consumers/connections and a restorable retained backup.
  Delete only manifest-listed migrated application objects and obsolete application
  history in `defaultdb`. Unexpected dependencies stop cleanup; no blind cascade.
- Preserve infrastructure-owned objects, other databases, valid credentials and
  the old secret versions required by the agreed recovery retention policy.

## Tech stack and project structure

Use existing Python 3.12+, asyncpg/SQLAlchemy, pytest and Ruff tooling. The current
database image pins Liquibase 5.0.4; current disposable tests use PostgreSQL 17.
Rehearse with the actual Aiven major version too if different. No dependency or
provider upgrade is implicit.

| Location | Responsibility |
| --- | --- |
| `database/` | Provisioning SQL, domain changelog entry points, schema-relocation changesets and migration runbook. |
| `database/scripts/`, `database/tests/` (proposed) | Copy/verification tooling and synthetic migration rehearsals. |
| `apps/backend/market-scanner-adk/src/test/integration/` | Scanner persistence and migration integration coverage. |
| `apps/backend/market-scanner-api/src/test/integration/` | Reader contract and access checks. |
| Momentum branch's `apps/backend/momentum-adk/` | Persistent session schema, runtime and integration tests. |
| `infra/`, `infra/reader/`, `infra/litellm/` | Versioned runtime secret references and deployment configuration. |
| `docs/specs/database-per-application.md` | This specification. |
| `tasks/plan.md`, `tasks/todo.md` | Subsequent approved plan/tasks; preserve existing feature documents when replacing them. |

## Commands

Existing commands below are executable from the indicated directories. They are
validation commands, not a production migration runbook. Commands for new copy,
partition, fence, rollback and cleanup tooling must be specified during planning
and implemented/tested before operations; that tooling does not exist yet.

```sh
# Repository root: documentation hygiene and current database image.
git diff --check
docker build -t local/deep-copy-liquibase:5.0.4 database

# database/: requires a protected local .env selecting an explicit TEST target.
docker compose --profile migration run --rm liquibase validate
docker compose --profile migration run --rm liquibase update-sql

# apps/backend/market-scanner-adk/: existing local checks.
uv sync --frozen
TZ=UTC uv run --frozen pytest -q src/test/unit
uv run --frozen ruff check src

# Repository root: existing Terraform validation without a remote backend.
terraform fmt -check -recursive infra
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
terraform -chdir=infra test
terraform -chdir=infra/reader init -backend=false
terraform -chdir=infra/reader validate
terraform -chdir=infra/reader test
```

Use the existing [disposable database procedure](../../database/README.md) for
Scanner integration tests. Its current single-database tests are a regression
baseline, not proof of cross-database isolation or this migration's completeness.

## Code style

Follow existing English documentation, Python typing, 88-column Ruff formatting,
explicit transactions and parameterized values. Quote SQL identifiers separately;
do not interpolate untrusted identifiers or secrets. Example from existing code:

```python
database_exists = await admin.fetchval(
    "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname='litellm')"
)
```

Operational output must be redacted and deterministic, for example:
`VERIFY market_scanner: table_counts=equal history=equal permissions=passed`.
Failures must return nonzero without exposing credentials or row contents.

## Testing strategy and success criteria

Use pytest with disposable PostgreSQL and real pinned Liquibase. Test fixtures
include both domains' histories, nested session JSON, timestamps, related report
rows and sequence-backed objects where present. Run both fresh-install and copied
database scenarios. No skipped required integration tests count as a pass.

| ID | Required proof before declaring the migration complete |
| --- | --- |
| DB-01 | Live inventory maps every application object and every deployed consumer; unknown items are resolved. |
| DB-02 | One database per domain exists on the same service; effective privileges enforce cross-domain isolation and prevent readers accessing sessions, including inherited/PUBLIC rights. Workers and readers cannot perform DDL or access Liquibase metadata. |
| DB-03 | For each copied table, equivalent structure under the approved schema mapping and identical row count plus deterministic full-content comparison at the fenced snapshot; counts alone are insufficient. Keys, constraints, indexes, sequence state and ACLs match the intended manifest. |
| DB-04 | Each Liquibase history contains exactly its preserved original domain subset plus approved new relocation entries. Checksums/identities remain unchanged, lock state is valid, repeated update is a no-op, and fresh/imported installations plus independent forward/rollback tests reach the expected layouts. |
| DB-05 | Scanner writes durably to `results`; after restart the reader fetches the unchanged report contract. Momentum session/event read-append-restart works in `_sessions` with one pooled session connection; all SDK tables and metadata stay there. |
| DB-06 | Runtime identities and pinned secret references prove all consumers use their target; no application remains connected to source and no pool budget increase occurs. |
| DB-07 | Rehearsals prove backup restoration and rollback before writes; a post-write rollback rehearsal proves no lost updates/deletes, or write resumption is blocked until recovery is defined and tested. |
| DB-08 | Wrong host/database, occupied target, unknown history, checksum mismatch, interrupted restore, failed validation and active source writers each fail safely with redacted diagnostics. |
| DB-09 | Observation window and scheduled/synthetic operations pass; cleanup removes only mapped application objects. Live inventory confirms `defaultdb` has no application data. |
| DB-10 | Repository config/examples/runbook reflect domain databases, results/sessions separation, independent domain changelogs and exact recovery commands; evidence distinguishes local, CI and deployed results. |
| DB-11 | Final target inventory has Scanner business tables in `results` and optional SDK tables in `sessions`; Momentum analyses are in `_analysis` and all SDK tables in `_sessions`; migration metadata stays in each domain's `liquibase`; no legacy domain-schema application objects remain. LiteLLM retains its native layout. |
| DB-12 | A synthetic session can be expired/deleted without deleting or making its associated business result unreadable. The result-only reader can fetch that result but cannot query any session/state/event table. |

Local synthetic tests must also prove that retrying provisioning is safe and that
a partial copy cannot be promoted or mistaken for a completed migration. Retain
redacted verification evidence, not raw dumps or application data, for review.

## Boundaries

- **Always:** preserve dirty/unrelated worktrees; use versioned infrastructure and
  migration tooling; validate explicit source/target identity; keep encrypted/TLS
  connections and secret hygiene; verify data before opening writes; respect the
  repository's one-application-component and 1,000-counted-line PR limits.
- **Ask first:** validate this spec before planning, then validate plan and tasks
  before implementation, as required by the invoked skill. Obtain the maintenance
  window and review the concrete deployment/cleanup evidence before irreversible
  execution. Revisit the spec if zero downtime, ownership or scope changes.
- **Never:** commit credentials, dumps or private data; overwrite occupied targets;
  rewrite applied migration history to silence failures; delete source data before
  verified recovery; broaden runtime permissions; declare deployment from code alone.

## Open decisions and next gate

1. Is a bounded write interruption acceptable? What maximum duration/window?
2. Is the proposed 24-hour minimum observation period sufficient? Backup retention
   and post-cleanup recovery requirements must be fixed before live execution.
3. Which deployed Momentum source and branch successor are authoritative? Inventory
   must establish this rather than inferring it from an unmerged worktree.

The [technical plan](../../tasks/plan.md) is approved. Next gate: human review of
the [task checklist](../../tasks/todo.md); implementation follows task approval. The overall
migration remains incomplete until DB-01 through DB-12 have direct evidence.

## Primary references

- [PostgreSQL database organization](https://www.postgresql.org/docs/current/manage-ag-overview.html)
  and [schemas](https://www.postgresql.org/docs/current/ddl-schemas.html): use
  databases for independent domains and schemas/permissions for related stores.
- [PostgreSQL pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html):
  selected-schema exports do not automatically include outside dependencies;
  global roles require separate handling.
- [PostgreSQL privileges](https://www.postgresql.org/docs/current/ddl-priv.html):
  inspect effective ownership, PUBLIC and role-derived privileges.
- [Liquibase DATABASECHANGELOG](https://docs.liquibase.com/concepts/basic/databasechangelog-table.html):
  changeset identity includes ID, author and filename; preserve execution/checksum metadata.
