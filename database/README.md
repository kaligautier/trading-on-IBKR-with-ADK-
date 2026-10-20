# Domain databases

PostgreSQL databases are separated by application. Both use `_sessions` for ADK
state/events, `_analysis` for business results, and `liquibase` for migration history.

| Database | Runtime role | Analysis storage | Liquibase entry point |
| --- | --- | --- | --- |
| `market_scanner` | `market_scanner_writer` | Report v3, assets, horizons | `db.changelog-scanner.yaml` |
| `momentum` | `momentum_writer` | Namespace reserved; implementation pending | `db.changelog-momentum.yaml` |

The Scanner API and scheduled job both persist sessions. A scheduled execution ID
can run once; an existing ID fails explicitly, including after a partial failure.
Start a new execution to rerun. Session and report writes are separate transactions:
a failed report write leaves session evidence, but never a successful job result.
Deleting a session does not delete its report. `market_scanner_reader` reads analyses
only. The ADK SDK cannot create tables or update its schema metadata at runtime.

## Apply and test locally

From the repository root with Docker on a local Unix socket and uv installed:

```sh
uv sync --project apps/backend/market-scanner-adk --frozen --python 3.12
uv sync --project apps/backend/market-scanner-api --frozen --python 3.12
python3 database/scripts/rehearse_domains.py
```

The rehearsal creates `deepcopy-domains-test` on `127.0.0.1:55461`, rebuilds only
`market_scanner` and `momentum`, applies each Liquibase chain twice, then exercises
the actual ADK, API, report storage and reader. Model/data providers are simulated;
these tests do not generate real market research or call LiteLLM. Regression-test
containers on ports 55462/55463 are removed afterward. The domain databases remain
available for inspection. Local credentials are disposable fixtures, never live secrets.

If Momentum is in a separate worktree, install its locked Python 3.12 dependencies
and pass `--momentum-root /path/to/worktree`. When its package is present in this
checkout, the rehearsal runs it automatically. Without that package, the shared
Momentum schema/SDK tests still run and the missing adapter suite is reported.

Explicit local controls:

```sh
python3 database/scripts/local_domains.py reset
python3 database/scripts/local_domains.py migrate --domain market_scanner
python3 database/scripts/local_domains.py migrate --domain momentum
python3 database/scripts/local_domains.py stop
```

`reset` erases both **owned local domain databases**. The harness refuses remote
Docker endpoints, unexpected labels and public port bindings. It never accepts a
remote database URL or uses `defaultdb`. It does not touch LiteLLM.

For the local Scanner `.env`, set:

```dotenv
MARKET_SCANNER_DATABASE_URL=postgresql://market_scanner_writer:domain-test-only@127.0.0.1:55461/market_scanner
DATABASE_SCHEMA=_analysis
```

The reader uses the same database with `market_scanner_reader` and the disposable
password `domain-test-only`. Momentum uses `momentum_writer` in database `momentum`.
Live provider credentials are needed only for a real market scan.

Build and verify the Scanner image, including an actual process restart and a
persisted session read, without external provider calls:

```sh
docker build -t local/scanner-domain:verify apps/backend/market-scanner-adk
python3 scripts/scanner_image_smoke.py local/scanner-domain:verify
```

## Provisioning and migrations

Create application databases and login roles through the owning administration
process. Run `domain-bootstrap.sql` as administrator with validated `domain` and
`writer` psql variables; add the Scanner reader CONNECT grant separately. Runtime
credentials must never own database/schema objects. Each database has an independent
history. There is no shared master, legacy schema fallback or data-copy migration.

Copy `.env.example` to an ignored `.env` and select exactly one database URL and its
matching changelog. Keep remote TLS verification enabled. From `database/`:

```sh
docker compose --profile migration build
docker compose --profile migration run --rm liquibase validate
docker compose --profile migration run --rm liquibase update
```

Migration selection is explicit. Changing only the changelog without changing the
connection URL does not select another database.

Each Scanner process holds at most one session connection plus the configured
analysis pool (default one). The local writer role limit of four accommodates one
API process and one job. Revision overlap or simultaneous extra jobs require a
larger reviewed budget or stopped consumers. Reader pool default is one; Momentum
session pool is one. Both engines close on shutdown. Service-wide live capacity,
new immutable images and numeric secret versions must be checked before rollout.

This change applies **locally**. It does not rebuild remote `defaultdb`, deploy Cloud
Run, change remote secrets, or run a live market scan. See
[local evidence](../docs/migrations/domain-databases/local-evidence.md).
