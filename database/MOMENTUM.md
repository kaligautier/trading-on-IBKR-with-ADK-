# Momentum PostgreSQL and Liquibase

## One supported installation

Use one database named `momentum` on the existing PostgreSQL server.
`changelog/momentum.yaml` is the only Liquibase entrypoint for a current deployment.
It includes `_sessions` (five ADK tables) and `_analysis` (twelve result tables).
Liquibase tracks applied changes in the separate `liquibase` schema.

| Identity | Purpose | Permissions |
| --- | --- | --- |
| Aiven administrator | Create the database/logins and run the one-time bootstrap | Provisioning only; never used by the worker |
| `database_migrator` | Own schema objects and run Liquibase | DDL and explicit grants; never used by the worker |
| `momentum_sessions_writer` | Persist ADK sessions, state and events | Enumerated DML in `_sessions`; no DDL/TEMP |
| `momentum_results_writer` | Store completed financial analyses | INSERT/SELECT in `_analysis`; no UPDATE/DELETE/DDL/TEMP |

Both runtime URLs explicitly name `/momentum`. Each pool has size one and no
overflow; each runtime login is limited to two connections. These limits share
the server's total connection budget, including administrator/migration clients.
Passwords belong in Secret Manager or ignored, mode-0600 local files.

## One-time DBA preparation

1. Create database `momentum` and the three non-administrative login roles above.
   Use separate credentials. Runtime roles must not own the database or belong
   to other roles. On an existing service, inspect effective PUBLIC grants too.
2. Connect as the administrator **to `momentum`** and execute
   `momentum-unified-bootstrap.sql` with `psql -v ON_ERROR_STOP=1 -f ...`.
   It checks the database, isolates CONNECT/CREATE/TEMP permissions and sets role
   timeouts/search paths. Run bootstrap against an existing database only after
   reviewing its affected roles and grants.
3. Reconnect as `database_migrator` and execute `momentum-unified-migrator.sql`.
   It creates the owned Liquibase schema. Aiven's administrator is not a PostgreSQL
   superuser and cannot assume an existing isolated migration identity.
4. Run the migration workflow below. The application does not create tables or
   migrate schemas at startup.

Provisioning credentials are separate from migration credentials. Supply them
through a protected PostgreSQL service/password file or environment; do not put
passwords in shell history, SQL examples, PRs or Terraform variables.

## Daily developer/operator workflow

Run from `database/`. Prepare an ignored migration environment file once:

```sh
cp momentum.env.example .env.momentum
chmod 600 .env.momentum
# Fill in the explicit momentum JDBC URL and database_migrator password.
```

Use the pinned Liquibase container and the dedicated Compose override:

```sh
lb() {
  docker compose --env-file .env.momentum \
    -f compose.yaml -f compose.momentum.yaml --profile migration "$@"
}
lb build
lb run --rm liquibase validate
lb run --rm liquibase status --verbose
lb run --rm liquibase update-sql
# Review the SQL and confirm the target/backup before applying a live migration.
lb run --rm liquibase update
lb run --rm liquibase status --verbose
```

The override fixes the changelog to `momentum.yaml`. Changeset preconditions also
reject a database whose name is not `momentum`. Verify the host, port and identity
in the protected environment: the database-name guard does not identify a server.
Use TLS for remote connections; preserve the environment's certificate policy.

## Making the next schema change

- Add a new formatted-SQL changeset under `changelog/momentum-unified/` and include
  it from `momentum.yaml` in order. Use a unique author/id and schema-qualified SQL.
- Keep already-applied files, paths and checksums unchanged. Do not use
  `clear-checksums` or `changelog-sync` to hide an unexpected mismatch.
- Grant only the privileges the runtime needs in that changeset. A new table does
  not automatically inherit the grants from previous tables.
- Prefer additive changes. For incompatible changes, add the new representation,
  backfill and switch consumers before a separately reviewed removal.
- Assess locks and data volume. Use bounded lock/statement timeouts and a separate
  plan for long backfills or operations requiring non-transactional execution.
- Write and test an explicit rollback, or document why the change needs a forward
  fix/backup restore. The initial schema rollback drops tables and their data;
  it is a disposable-test operation, not a way to undo a production analysis.

Before a live change, keep a protected backup and verify the restore procedure
against an isolated database. Preview rollback SQL before any rollback. Diagnose
an existing Liquibase lock before releasing it; do not clear it while a migration
is running. A successful `validate` checks the changelog, not application behavior
or the completeness of a backup.

## Local verification and post-deployment checks

From the repository root, with Docker running:

```sh
bash apps/backend/momentum-adk/scripts/test_database.sh start
MOMENTUM_TEST_ADMIN_URL=postgresql://postgres:local-test-only@127.0.0.1:55449/postgres \
MOMENTUM_TEST_CONTAINER=momentum-test-db \
TZ=UTC uv run --project apps/backend/momentum-adk --frozen pytest \
  -c apps/backend/momentum-adk/pyproject.toml -q apps/backend/momentum-adk/tests/integration
bash apps/backend/momentum-adk/scripts/test_database.sh stop
```

The fixture accepts only its labeled local container. Tests verify ownership,
effective grants, schema/ORM agreement, session lifecycle, atomic results,
rollback and preservation of Scanner data/checksums. After deployment, check
Liquibase status, then independently read a completed analysis and its correlated
session using the respective runtime identities; process exit zero alone is not
persistence proof.

## Historical compatibility

`changelog/momentum/`, `momentum-sessions.yaml`, `momentum-results.yaml` and their
old bootstrap scripts describe superseded layouts. They remain immutable because
they were applied and have regression tests. **Do not use them for a new Momentum
installation.** The supported target is always the unified root above.

The 97 imported historical analyses retain their original financial values and
IDs, with explicit `legacy` correlation markers. They have no corresponding ADK
sessions in this database. Data imports and their private backups are separate
from schema migrations.

References: [PostgreSQL privileges](https://www.postgresql.org/docs/current/ddl-priv.html),
[Liquibase update](https://docs.liquibase.com/community/reference-guide-5-0-4/init-update-and-rollback-commands/update),
[rollback previews](https://docs.liquibase.com/community/reference-guide-5-0/init-update-and-rollback-commands/what-are-rollback-commands).
