# Domain databases

The source of this layout is a read-only inspection of the working Aiven service on
23 October 2026, PostgreSQL 18.6. Each application owns a database; schemas separate
application state, analysis results, and migration metadata inside that database.

| Database | Schemas | Runtime identities | Migration owner |
| --- | --- | --- | --- |
| `market_scanner` | `_analysis`, `_sessions`, `liquibase` | `market_scanner_writer`, `market_scanner_reader` | `database_migrator`, Liquibase |
| `momentum` | `_analysis`, `_sessions`, `liquibase` | `momentum_sessions_writer`, `momentum_results_writer`, `momentum_results_reader` | `database_migrator`, Liquibase |
| `litellm` | `public` | `litellm` | Official LiteLLM image, Prisma |

Scanner has three analysis tables and five ADK tables; Momentum has twelve analysis
tables and five ADK tables. LiteLLM's upstream schema stays in its dedicated database;
application Liquibase never manages it. Provider-internal databases are outside this layout.

## Where things belong

```text
database/
  domains.json                 # Verified Aiven fingerprints and runtime roles
  domains/<domain>/
    bootstrap.sql              # Administrator: database access and role limits
    baseline.sql               # Current Aiven schemas, constraints, indexes and grants
    changelog.yaml             # One Liquibase entry point per application database
    migrations/                # Changes after the baseline
  operations/                  # Migration preparation and read-only catalog checks
  testing/                     # Disposable PostgreSQL lifecycle and full rehearsal
  tests/                       # Baseline, adoption, isolation and tool safety tests
  manage.py                    # The operator interface
```

Only the domain entry points above are supported. The superseded shared-database,
split-Momentum-database, and cutover files have been removed; Git preserves their
history. No supported changelog spans multiple application databases.

## Existing Aiven databases

The schema-only baselines were exported with PostgreSQL 18.6 `pg_dump`. They contain
no business records, credentials, or hostnames. The single ADK schema-version row
is seeded because the SDK requires it. `domains.json` records fingerprints of both
managed schemas, including columns, nullability, defaults, constraints, indexes,
ownership, and effective object grants. Connection strings and business rows are
excluded. Database-level permissions and role limits are defined separately in
`bootstrap.sql`; those are not part of the object fingerprint. Verification and
adoption also check runtime role attributes, connection limits, CREATE/TEMP rights,
memberships, login capability, and effective CONNECT access to all other
connectable non-template databases, including `postgres`. Provider-controlled
template admission is verified separately by the managed reader network checks.

Use Python from a locked application environment and build the pinned migration image:

```sh
uv sync --project apps/backend/market-scanner-adk --frozen --python 3.12
docker build -t local/deepcopy-database:5.0.4 database
```

Keep an explicit PostgreSQL URL in an ignored regular file with permissions `0600`.
Use the appropriate identity and database name, `sslmode=verify-full`, and the Aiven
CA via `sslrootcert` or `--ca-file`. Never put a real URL in shell history or Git.

```sh
# Baseline comparison before adoption; runtime identities can inspect the catalog.
uv run --project apps/backend/market-scanner-adk --frozen python database/manage.py \
  verify-baseline --domain momentum --url-file .local/momentum.url --ca-file .local/aiven-ca.pem
```

To adopt the new baseline on an existing database, first back up its Liquibase
tracking tables and establish an exclusive migration window. Use `database_migrator`:

```sh
uv run --project apps/backend/market-scanner-adk --frozen python database/manage.py \
  adopt --domain momentum --url-file .local/momentum-migrator.url --ca-file .local/aiven-ca.pem
```

`adopt` refuses a structural or object-grant mismatch before invoking Liquibase.
It synchronizes only through tag `aiven-20261023`; it does not run baseline DDL or
mark pending changes as applied. Existing tracking rows are retained for audit.
No adoption or schema changes were executed on Aiven as part of this repository reorganization.

## Fresh installation

An administrator creates the selected database and its non-administrative logins,
sets passwords outside source control, and executes that domain's `bootstrap.sql`.
Reconnect as `database_migrator` and execute `operations/prepare.sql` to create the
owned `liquibase` schema. These are distinct identities because an Aiven administrator
cannot necessarily assume an existing migration role.

Run `manage.py baseline --domain <domain> --url-file <private-file>` to create exactly
the captured Aiven state, stopping at `aiven-20261023`. Run `verify-baseline` afterward,
then `plan`, `migrate` and `verify` to reach and verify the current release.
An initial baseline has no destructive rollback: restore a protected backup for a live
recovery, or recreate an explicitly owned disposable test database.

## Managed template database admission

Some managed PostgreSQL services retain PUBLIC CONNECT on their `postgres`-owned
`template1` while denying actual connections through `pg_hba.conf`. Do not revoke
provider-owned privileges or exempt application databases. The bootstrap stays
strict by default. For this specific template only, first grant the new reader
CONNECT on `momentum` so its credentials can be positively verified, then run:

```sh
umask 077
uv run --project apps/backend/momentum-api --frozen python \
  apps/backend/momentum-api/scripts/verify_reader_network.py \
  --reader-url-file "$READER_URL_FILE" > "$ADMISSION_SQL"
```

The private URL file must use verified TLS and a local readable CA path. The
verifier first connects successfully to Momentum, then attempts every other
connectable database with that same reader identity. Unexpected errors, bad
credentials, timeouts or any successful cross-database connection stop it. Only
an explicit `pg_hba.conf` refusal on the system-owned template emits a session
attestation. Immediately execute that generated SQL and
`database/domains/momentum/bootstrap.sql` on the same administrator connection. Do not
store the attestation in database/role defaults or set it manually. Repeat this
verification on deployment and after any managed network/access-policy change.
The attestation never exempts another database or changes network permissions.


## Subsequent changes

Use `status` to inspect pending changes, `plan` to review generated SQL, and `migrate`
to apply them. All commands take the same explicit domain and private URL file.
After adoption, add a new migration under that domain's `migrations/` directory and
include it in its `changelog.yaml`. Keep the baseline and applied changes immutable.
Do not clear checksums to hide a mismatch.

The current Momentum snapshot includes nullable sentiment scores and the consultation
reader's allowlisted grants and indexes, verified on Aiven during the final inspection.
The baseline remains immutable. Momentum now has an additive migration for private
trading memory in `_analysis.trading_memory`; consultation readers receive no grant
on that table. Adopt the baseline before applying subsequent migrations to an
existing installation. `verify-baseline` compares the immutable adoption snapshot;
`verify` checks the current release's schema, grants, runtime policy and every
expected Liquibase identity/checksum. Use `database_migrator` for `verify` because
runtime identities intentionally cannot read migration history. Verification is
read-only and permits retained historical rows from pre-baseline migrations.
It rejects missing changesets, null/changed checksums and structural drift.
Do not update the baseline fingerprint to conceal a migration.
Memory migration is forward-only once populated; rolling back application images
must preserve retained decisions/reflections.

The legacy Trader ratio migration remains included with its deployed logical path
and forward SQL. Its rollback deliberately keeps `TEXT` (`SELECT 1`) because the
baseline already has that type and completed results may exceed twenty characters.
Only the rollback directive changes; a real replay test validates the old checksum
and proves rollback/reapply preserve long explanations. Do not add comments inside
the applied forward SQL: Liquibase can include them in its checksum.

Each domain's `current.json` is generated from a fresh, fully migrated local
database, not from production. After adding a migration, regenerate and review it:

```sh
uv run --project apps/backend/market-scanner-adk --frozen python \
  database/testing/refresh_current.py
```

This command resets only the labelled disposable domain fixture. It never accepts
a remote URL. Commit the new manifest with the migration, leaving `baseline.sql`
and the baseline fingerprints in `domains.json` unchanged. `verify` rejects a stale
manifest if the SQL/changelog sources changed; CI independently replays the chain
and compares both schema fingerprint and history to the committed manifest.

## Required merge check

The `Database migrations` check runs the full rehearsal on **every PR**, on pushes
to `main`, and on manual dispatch. It has no path filter, conditional job or
continue-on-error step. Documentation-only PRs therefore emit the same check.
Require this exact check name, from the GitHub Actions app, in `main` branch
protection alongside existing checks. Keep strict/up-to-date validation enabled.
The workflow defines execution; repository branch protection enforces merging.
When enabling it, preserve existing required checks and other protection settings.
Open PRs based on an older workflow need an update/rebase to emit the new name.

## Local verification

```sh
uv sync --project apps/backend/market-scanner-adk --frozen --python 3.12
uv sync --project apps/backend/market-scanner-api --frozen --python 3.12
uv sync --project apps/backend/momentum-adk --frozen --python 3.12
uv sync --project apps/backend/momentum-api --frozen --python 3.12
python3 database/testing/rehearse.py
python3 database/testing/local_domains.py stop
```

The rehearsal uses pinned PostgreSQL 18 on a local Unix-socket Docker daemon. It
rebuilds only labelled disposable fixtures, checks exact Aiven-baseline equivalence,
proves adoption preserves application rows and rejects drift, and runs the real
application persistence and reader suites. Local fixtures explicitly disable TLS;
remote management requires certificate and hostname verification. No providers or
LLMs are called. The retained domain fixture binds only to `127.0.0.1:55471`.

References: [Liquibase baseline synchronization](https://docs.liquibase.com/community/reference-guide-5-0/database-inspection-change-tracking-and-utility-commands/changelog-sync),
[PostgreSQL schema-only exports](https://www.postgresql.org/docs/18/app-pgdump.html),
[LiteLLM migration ownership](../infra/litellm/README.md).
