# Domain databases

The source of this layout is a read-only inspection of the working Aiven service on
23 October 2026, PostgreSQL 18.6. Each application owns a database; schemas separate
application state, analysis results, and migration metadata inside that database.

| Database | Schemas | Runtime identities | Migration owner |
| --- | --- | --- | --- |
| `market_scanner` | `_analysis`, `_sessions`, `liquibase` | `market_scanner_writer`, `market_scanner_reader` | `database_migrator`, Liquibase |
| `momentum` | `_analysis`, `_sessions`, `_suggestions`, `liquibase` | `momentum_sessions_writer`, `momentum_results_writer`, `momentum_results_reader` | `database_migrator`, Liquibase |
| `litellm` | `public` | `litellm` | Official LiteLLM image, Prisma |

Scanner has three analysis tables and five ADK tables; Momentum has thirteen analysis
tables (twelve in the baseline plus `trading_memory` from migration 001), five ADK tables
and the `_suggestions.ticker_suggestions` table from migration 002. LiteLLM's upstream schema stays in its dedicated database;
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
    current.json               # Fingerprint and changesets of the current release
  operations/
    prepare.sql                # database_migrator: the owned liquibase schema
    verify.sh                  # Read-only baseline/current checks (psql, jq)
    liquibase.sh               # Liquibase CLI as database_migrator, from a private env file
  capacity/                    # Shared 15-connection budget (jq)
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

The operator tools are the PostgreSQL 18 `psql` client, `jq` and the Liquibase CLI,
run from the pinned image `database/Dockerfile` builds (Liquibase 5.0.4 with a
checksum-pinned JDBC driver). No application environment is needed.

`verify.sh` connects through libpq: define a service in `~/.pg_service.conf` with the
host, port, user, `sslmode=verify-full` and the Aiven CA as `sslrootcert`, keep the
password in `~/.pgpass` (`0600`), and select it with `PGSERVICE`. `liquibase.sh` reads a
private (`0600`) docker env file with `LIQUIBASE_COMMAND_URL` (the domain database,
`sslmode=verify-full&sslrootcert=/run/database-ca.pem`), `LIQUIBASE_COMMAND_USERNAME=database_migrator`
and `LIQUIBASE_COMMAND_PASSWORD`; it mounts `DATABASE_CA_FILE` at that path. Both refuse
another database, and `liquibase.sh` refuses another identity, unverified remote TLS
and destructive commands. Never put a real URL or password in shell history or Git.

```sh
# Baseline comparison before adoption; runtime identities can inspect the catalog.
PGSERVICE=momentum-aiven database/operations/verify.sh baseline momentum
```

To adopt the new baseline on an existing database, first back up its Liquibase
tracking tables and establish an exclusive migration window. Use `database_migrator`:

```sh
PGSERVICE=momentum-aiven-migrator database/operations/verify.sh baseline momentum
DATABASE_ENV_FILE=.local/momentum-migrator.env DATABASE_CA_FILE=.local/aiven-ca.pem \
  database/operations/liquibase.sh momentum changelog-sync-to-tag --tag=aiven-20261023
```

Run adoption only after `verify.sh baseline` succeeds; it fails on any structural,
object-grant or runtime-role mismatch. `changelog-sync-to-tag` only records the
baseline changesets: it runs no DDL and does not mark later changes as applied.
Existing tracking rows are retained for audit. The `Database operator checks` workflow
rehearses this sequence on a disposable database and proves the baseline catalog is
unchanged by adoption.
No adoption or schema changes were executed on Aiven as part of this repository reorganization.

## Fresh installation

An administrator creates the selected database and its non-administrative logins,
sets passwords outside source control, and executes that domain's `bootstrap.sql`.
Reconnect as `database_migrator` and execute `operations/prepare.sql` to create the
owned `liquibase` schema. These are distinct identities because an Aiven administrator
cannot necessarily assume an existing migration role.

Run `liquibase.sh <domain> update-to-tag --tag=aiven-20261023` to create exactly the
captured Aiven state, then `verify.sh baseline <domain>`. Then `update-sql` to review,
`update`, and `verify.sh current <domain>` reach and verify the current release.
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

Use `liquibase.sh <domain> status --verbose` to inspect pending changes, `update-sql`
to review the generated SQL, and `update` to apply them, then `verify.sh current`.
After adoption, add a new migration under that domain's `migrations/` directory and
include it in its `changelog.yaml`. Keep the baseline and applied changes immutable.
Do not clear checksums to hide a mismatch.

The current Momentum snapshot includes nullable sentiment scores and the consultation
reader's allowlisted grants and indexes, verified on Aiven during the final inspection.
The baseline remains immutable. Momentum now has an additive migration for private
trading memory in `_analysis.trading_memory`; consultation readers receive no grant
on that table. Adopt the baseline before applying subsequent migrations to an
existing installation. `verify.sh baseline` compares the immutable adoption snapshot;
`verify.sh current` checks the current release's schema, grants, runtime policy and every
expected Liquibase identity/checksum. Use `database_migrator` for `verify.sh current` because
runtime identities intentionally cannot read migration history. Verification is
read-only and permits retained historical rows from pre-baseline migrations.
It rejects missing changesets, null/changed checksums and structural drift.
Current-release verification also includes explicit column privileges from
[`pg_attribute.attacl`](https://www.postgresql.org/docs/18/catalog-pg-attribute.html),
expanded with [`aclexplode`](https://www.postgresql.org/docs/18/functions-info.html#FUNCTIONS-ACL).
Grantee names, privilege types and grant options are sorted independently of
database object OIDs and ACL entry order. This covers both an unexpected reader
grant on a private column and a missing writer UPDATE grant, alongside table ACLs.
PostgreSQL documents these column-level permissions under
[`GRANT`](https://www.postgresql.org/docs/18/sql-grant.html).
The fingerprint is a project verification mechanism, not a PostgreSQL migration
requirement. The baseline check and adoption retain their original catalog format
and fingerprints; they do not gain column-ACL coverage. Only current-release
manifests are regenerated for this extended check, with no baseline or applied
migration changes.
Do not update the baseline fingerprint to conceal a migration.
Memory migration is forward-only once populated; rolling back application images
must preserve retained decisions/reflections.

The legacy Trader ratio migration remains included with its deployed logical path
and forward SQL. Its rollback deliberately keeps `TEXT` (`SELECT 1`) because the
baseline already has that type and completed results may exceed twenty characters.
Only the rollback directive changes; a real replay test validates the old checksum
and proves rollback/reapply preserve long explanations. Do not add comments inside
the applied forward SQL: Liquibase can include them in its checksum.

Each domain's `current.json` records the current release's fingerprint (column grants
included) and changesets, taken from a fresh, fully migrated local database, never from
production. After adding a migration, the `Database operator checks` workflow fails
and prints the new fingerprint (`verify.sh current` on its current-release database);
review it, update `fingerprint` and add the new changesets from `history.tsv`. Leave
`baseline.sql` and the baseline fingerprints in `domains.json` unchanged.

## Liquibase-only check (replacing the Python tooling)

The `Liquibase migrations` workflow (`.github/workflows/database-liquibase.yml`) uses
only the Liquibase CLI, `psql` and `pg_dump` on a disposable PostgreSQL 18. For each
domain it runs `bootstrap.sql` and `operations/prepare.sql`, then `liquibase validate`,
`update-to-tag aiven-20261023`, `update`, a second `update` and `status` (which must be
up to date). It then compares, for every domain that has them:

- `schema.sql`: `pg_dump --schema-only --create` without comment lines. It covers
  tables, constraints, indexes, ownership, table and column grants, and per-database
  role settings (`search_path`, timeouts).
- `history.tsv`: `id`, `author`, `filename` and `md5sum` of every applied changeset.

After adding a migration, regenerate both files from a fresh local replay and review
the diff: run the `domain-database` action's script
(`.github/actions/domain-database/action.yml`) with `NAME`, `PORT`, `DOMAINS`,
`PASSWORD`, `IMAGE` and `RUNNER_TEMP` set as in its inputs, then the workflow's
comparison step, and copy `$RUNNER_TEMP/<domain>.schema.sql` and `.history.tsv` over
the committed files. A failing CI run prints the same diff. Never point these steps
at Aiven. Application workflows reuse the same action for their database tests.

The remaining Python rehearsal below (`testing/`, `tests/`) is superseded by these
workflows and the application workflows, and is being removed.

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
rebuilds only labelled disposable fixtures and runs the real application persistence
and reader suites. Baseline equivalence, adoption and drift rejection are rehearsed by
the `Database operator checks` workflow. Local fixtures explicitly disable TLS;
remote management requires certificate and hostname verification. No providers or
LLMs are called. The retained domain fixture binds only to `127.0.0.1:55471`.

References: [Liquibase baseline synchronization](https://docs.liquibase.com/community/reference-guide-5-0/database-inspection-change-tracking-and-utility-commands/changelog-sync),
[PostgreSQL schema-only exports](https://www.postgresql.org/docs/18/app-pgdump.html),
[LiteLLM migration ownership](../infra/litellm/README.md).
