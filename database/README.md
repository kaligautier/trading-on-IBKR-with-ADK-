# Shared PostgreSQL migrations

The scanner writes a version 3 JSON report and normalized asset/horizon rows in
PostgreSQL. Each report is committed in one transaction. A failed asset write
rolls back the entire report. The application never creates or migrates tables.

## Existing database

An administrator must create the login roles `database_migrator`,
`market_scanner_writer`, and `market_scanner_reader`, assigning unique passwords
outside version control. Run `bootstrap.sql` once as the administrator. It
creates the Liquibase schema and configures role limits and search paths.

Copy `.env.example` to `.env` and set the JDBC URL and migration password. Then:

```sh
docker compose --profile migration build
docker compose --profile migration run --rm liquibase validate
docker compose --profile migration run --rm liquibase update
```

The changelog grants the writer INSERT access and the reader SELECT access.
Runtime services must use these roles, not the administrator or migration role.
Never run the initial changelog blindly against tables managed by another
migration system; establish a reviewed baseline first.

## Disposable integration tests

From the repository root, with Docker running:

```sh
docker build -t local/deep-copy-liquibase:5.0.4 database
docker run --rm -d --name scanner-test-db \
  -p 127.0.0.1:55439:5432 \
  -e POSTGRES_PASSWORD=local-test-only postgres:17
```

Wait for `docker exec scanner-test-db pg_isready -U postgres` to succeed. From
`apps/backend/market-scanner-adk`:

```sh
TZ=UTC \
MARKET_SHARED_TEST_DATABASE_URL=postgresql://postgres:local-test-only@127.0.0.1:55439/postgres \
MARKET_SHARED_TEST_CONTAINER=scanner-test-db \
uv run --frozen pytest -q
```

The tests cover report round trips with the current Liquibase schema, transactional
rollback, role permissions, pool limits, migration checksums, and rollback of
another domain. Providers and Gemini are mocked in these integration tests.
The test host must be localhost, and the shared-database tests require a fresh
server without pre-existing scanner roles. Stop it with
`docker stop scanner-test-db` when finished; its data is disposable.

## Dedicated Momentum databases

The current target uses two logical databases on the existing PostgreSQL service:

| Database | Runtime login | Data |
| --- | --- | --- |
| `momentum_sessions` | `momentum_sessions_writer` | ADK sessions, state and events |
| `momentum_results` | `momentum_results_writer` | Completed financial analyses |

Provision these NEW databases and login passwords through the administrator
procedure. Run `momentum-databases-bootstrap.sql` once in each database as the
administrator. It refuses other database names, removes PUBLIC CONNECT/TEMP,
grants only the matching runtime CONNECT, and creates the migrator-owned
Liquibase schema. Runtime roles have no memberships, DDL or TEMP privileges and
are limited to two connections each. They cannot connect to each other's database.
The shared service connection limit still applies across all databases/instances.

Run migrations using `database_migrator` and the explicit dedicated JDBC URL:

```sh
# Session database only; never point this command at defaultdb.
liquibase --changelog-file=momentum-sessions.yaml update
# Result database only.
liquibase --changelog-file=momentum-results.yaml update
```

Each root has its own Liquibase history and excludes Scanner. Configure session
and result URLs explicitly with their own runtime credentials; do not derive URLs
or fall back to the legacy database. Keep credentials in ignored local files or
Secret Manager. Live creation, copying the retained verification session, switching
credentials and legacy cleanup are separate from local migration tests.

## Legacy shared Momentum foundation

The following describes the previously applied foundation; it is preserved for
history and compatibility, not the target for new worker deployments.


Momentum uses the same application database, in its own `momentum` schema.
The separate `litellm` database is not a migration target. Liquibase owns all
objects as `database_migrator`; the non-owner `momentum_writer` login receives
only enumerated runtime permissions. Create its password through the existing
administrator procedure; do not commit credentials.

Before bootstrap, audit effective PUBLIC privileges and role memberships.
PostgreSQL rights are additive: a direct REVOKE cannot cancel a PUBLIC grant.
If PUBLIC grants TEMPORARY, review `momentum-public-privileges.sql`: it preserves
that right explicitly for current logins except `momentum_writer`, then revokes
the implicit PUBLIC grant in the current database. Future logins must opt in.
It does not change another database or grant access to application tables.
Run that reviewed correction as an administrator, then `momentum-bootstrap.sql`.
Bootstrap rejects administrative/inherited privileges and effective CREATE/TEMP.
Apply the shared Liquibase changelog as the migration identity afterwards.
Momentum changesets require an explicit context, so existing Scanner migration
commands keep their original behavior. Use `liquibase update --context-filter=momentum`
(or `LIQUIBASE_COMMAND_CONTEXT_FILTER=momentum` with Compose). The initial Scanner
changeset stays unchanged; existing checksums are preserved.

Run the Momentum suite against its dedicated disposable server:

```sh
bash apps/backend/momentum-adk/scripts/test_database.sh start
MOMENTUM_TEST_ADMIN_URL=postgresql://postgres:local-test-only@127.0.0.1:55449/postgres \
MOMENTUM_TEST_CONTAINER=momentum-test-db \
TZ=UTC uv run --project apps/backend/momentum-adk --frozen pytest \
  -c apps/backend/momentum-adk/pyproject.toml -q apps/backend/momentum-adk/tests/integration
bash apps/backend/momentum-adk/scripts/test_database.sh stop
```

The fixture requires the named/labeled loopback-only container on port 55449,
rejects existing test roles and never accepts remote URLs. Integration variables
are required; missing prerequisites fail rather than skip. It applies the real
shared migrations in a unique database and removes only its own fixture objects.
