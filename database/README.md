# Scanner database

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
