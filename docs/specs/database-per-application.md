# Spec: One PostgreSQL database per application

Status: DRAFT — awaiting human specification review.
Date: 2026-10-20.
Base: `origin/main` at `9bbf570`; branch: `feat/database-per-app`.

## Objective

Move application data out of Aiven `defaultdb` into dedicated databases on the
existing PostgreSQL service. Preserve data, migration identity, runtime behavior,
and the ability to recover. The intended end state is:

```text
Existing Aiven PostgreSQL service
├── market_scanner
│   ├── market_scanner  (reports, assets, horizons)
│   ├── sessions        (only if persistent Scanner sessions exist)
│   └── liquibase       (Scanner migration history)
├── momentum
│   ├── momentum        (existing sessions and future results)
│   └── liquibase       (Momentum migration history)
├── litellm             (existing LiteLLM-managed objects and history)
└── defaultdb           (no application data after verified cleanup)
```

This replaces the shared-`defaultdb` design; it does not mean one database for
every technical schema. Scanner and Momentum each retain their own `liquibase`
schema. No new Aiven service, plan upgrade, PostgreSQL upgrade, or session-storage
feature is included. Capacity and connection budgets remain service-wide.
Pricing and current capacity must be checked before provisioning; no cost change
is asserted by this specification.

## Assumptions requiring review

- A bounded maintenance window may pause all affected writers and migrations.
  This is proposed, not yet approved. Zero downtime would require a revised design.
- Existing runtime role names and their intended permissions remain stable.
  Per-application migrator identities are not required by this migration; the
  existing `database_migrator` may administer both application databases.
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
- Create independent Liquibase locking state after proving no migration is active;
  do not copy a held lock. Do not use `clearCheckSums`, blind `changelogSync`, or
  rerun creation changesets to hide inconsistent imported history.
- Already-applied entries must produce no application DDL on `update-sql`; a
  second `update` must be a no-op. Applying or rolling back a new migration in one
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
- Verify target identity from the actual runtime connection, plus a durable write
  and read after process restart. HTTP health, green CI and a Terraform plan alone
  do not prove successful migration.
- Resume writes only after copied data/history and permissions pass verification.
  Prevent simultaneous writable source and target generations.

### Rollback and cleanup

- Before target writes resume, rollback restores prior secret references and
  revisions, removes the source write fence and resumes the prior schedules.
  Preserve source data unchanged until this path has been rehearsed.
- Once target writes exist, merely restoring old URLs would lose data. Pause
  writers again, back up the target, reconcile every post-cutover change back to
  source under a tested procedure, validate equality, then switch. If this path
  is not proven, keep writes stopped and repair forward; never claim lossless rollback.
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
| `database/` | Provisioning SQL, application changelog entry points and migration runbook. |
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
| DB-02 | Target databases exist on the same service; role connection and object-access tests prove the intended isolation, including inherited/PUBLIC rights. |
| DB-03 | For each copied table, identical schema and row count plus deterministic full-content comparison at the fenced snapshot; counts alone are insufficient. Keys, constraints, indexes, sequence state and ACLs also match the intended manifest. |
| DB-04 | Each Liquibase history is exactly its approved subset; checksums/identities preserved, lock state valid, repeated update is a no-op and independent forward/rollback tests pass. |
| DB-05 | Scanner durable report write, restart and reader fetch preserve the existing report contract; Momentum session/event read-append-restart works with one pooled connection. |
| DB-06 | Runtime identities and pinned secret references prove all consumers use their target; no application remains connected to source and no pool budget increase occurs. |
| DB-07 | Rehearsals prove backup restoration and rollback before writes; a post-write rollback rehearsal proves no lost updates/deletes, or write resumption is blocked until recovery is defined and tested. |
| DB-08 | Wrong host/database, occupied target, unknown history, checksum mismatch, interrupted restore, failed validation and active source writers each fail safely with redacted diagnostics. |
| DB-09 | Observation window and scheduled/synthetic operations pass; cleanup removes only mapped application objects. Live inventory confirms `defaultdb` has no application data. |
| DB-10 | Repository config/examples/runbook reflect separate databases, independent changelogs and exact recovery commands; evidence distinguishes local, CI and deployed results. |

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

Next gate: human approval of this specification. The implementation plan and task
list have deliberately not been created or substituted for approval. The overall
migration remains incomplete until DB-01 through DB-10 have direct evidence.

## Primary references

- [PostgreSQL pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html):
  selected-schema exports do not automatically include outside dependencies;
  global roles require separate handling.
- [PostgreSQL privileges](https://www.postgresql.org/docs/current/ddl-priv.html):
  inspect effective ownership, PUBLIC and role-derived privileges.
- [Liquibase DATABASECHANGELOG](https://docs.liquibase.com/concepts/basic/databasechangelog-table.html):
  changeset identity includes ID, author and filename; preserve execution/checksum metadata.
