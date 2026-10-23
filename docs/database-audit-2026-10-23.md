# PostgreSQL management audit

Audit date: 23 October 2026. Audited revision: `80e4714`.

The PostgreSQL architecture has a sound foundation. The highest-priority improvements concern worker TLS, durable application memory, database CI coverage, and recovery readiness.

## Implementation follow-up

The database reorganization requested after the audit was delivered through PRs #154–#165, rebased and merged sequentially into `main`. This audit PR is the final documentation step. Each implementation PR changes at most one application component and no more than 1,000 counted lines. Existing CI policies remain unchanged. The findings below remain a dated record of the original checkout; this section identifies what the follow-up actually changes.

The former `database/` directory mixed three generations of installation paths: shared-database schemas, separate Momentum session/result databases, and the current database-per-domain layout. Multiple changelog roots, bootstrap scripts, Compose files, and completed cutover runbooks made it difficult to identify the supported path.

The replacement reduces `database/` from 49 to 24 files and uses the working Aiven PostgreSQL 18.6 catalogs captured on 23 October 2026 as the schema source:

- `market_scanner` and `momentum` each have their own database, with `_analysis`, `_sessions`, and `liquibase` schemas.
- Each application database has one bootstrap, schema-only baseline, and Liquibase entry point. LiteLLM keeps its separate database and upstream Prisma migration ownership.
- Historical migration and cutover files are removed from the active tree; Git retains their history.
- The operator interface verifies schema fingerprints and runtime access before adoption. Adoption preserves existing tracking rows and marks only the baseline; it does not replay application DDL.
- The current Momentum snapshot includes nullable sentiment scores and consultation reader grants/indexes. Its ORM text column is aligned with the live `risk_reward_ratio` column.
- The managed-template admission verifier and its regression coverage from `main` are preserved.

Validation before publication: 780 tests passed across database, Scanner, Scanner API, Momentum, and Momentum API suites; Scanner's packaged image also passed startup/restart and non-root checks. Read-only Aiven comparisons confirmed both domains' schemas, ownership, object grants, and checked runtime privileges. No remote schema adoption or business-data mutation was performed. After integrating the managed-admission correction from `main`, all 174 Momentum API tests passed, and the combined implementation passed its GitHub application, database and image checks. Each dependent PR also runs its own CI checks. Pre-merge review added regression coverage for unusable/elevated runtime roles, cancellation of timed-out Liquibase containers, cross-database connection grants, stopped test containers, and separate pool-timeout/concurrency assertions; transitional commands and documentation were repaired before their respective PRs landed. The pinned JDBC driver download uses the official pgJDBC host after repeated Maven Central failures; its version and SHA-256 remain unchanged.

This addresses the competing installation paths and extends database CI coverage. It does not claim to fix worker TLS, durable application memory, idempotency, LiteLLM owner privileges, or backup/restore readiness. See the [current database guide](../database/README.md) for installation and adoption.

## Integration order

The implementation PRs below were rebased onto updated `main` and merged in this order after their CI checks passed. Rebase merges preserve the linear history required by `main`. This audit is the final documentation PR.

| Order | PR | Scope |
| --- | --- | --- |
| 1 | [#154](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/154) | capture current Aiven domain baselines |
| 2 | [#155](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/155) | verify and adopt current domain baselines |
| 3 | [#156](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/156) | use current domain database baseline |
| 4 | [#157](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/157) | use current domain database baseline |
| 5 | [#158](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/158) | use current domain database baseline |
| 6 | [#159](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/159) | retire superseded topology tests |
| 7 | [#160](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/160) | use current domain database fixtures |
| 8 | [#161](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/161) | rehearse all current domain database consumers |
| 9 | [#162](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/162) | replace historical database rollout guides |
| 10 | [#163](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/163) | retire completed cutover utilities |
| 11 | [#164](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/164) | remove obsolete database topologies |
| 12 | [#165](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/165) | remove retired migration entry points |

## Scope and limitations

This audit covers Scanner, Momentum, and LiteLLM's PostgreSQL configuration: data access, transactions, Liquibase migrations, SQL privileges, and infrastructure configuration. Verification used the audited checkout and a disposable local PostgreSQL 17 server.

During the original audit, the active Aiven configuration, production identity privileges, and provider backups were not verified. The later catalog and access verification is described above; provider backups remain unverified. Deployment findings describe the repository configuration rather than observed production behavior. The Momentum consultation API added after the audited revision is outside the original audit scope.

**Publication update at `48ac681`:** the default branch has advanced since the audit. It now includes a [domain database CI workflow](../.github/workflows/domain-database.yml) that runs the [local rehearsal](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/48ac681/database/scripts/rehearse_domains.py), including Scanner writer integration tests. Finding 3 is therefore partially addressed. The historical test counts below belong to the original audit; they are not new test results for the publication revision. The source files underlying findings 1, 2, 5, and 6, and the analysis schemas discussed in finding 7, are unchanged between those two revisions.

## Existing strengths

- Scanner report writes and Momentum result writes use atomic transactions.
- Migrations are separate from application startup.
- SQLAlchemy pools have bounded sizes, no overflow, and explicit timeouts.
- Scanner separates reader and writer identities; Momentum separates session and result identities.
- The Scanner reader requires verified TLS for remote connections and uses read-only transactions.
- Current migrations create objects under the `database_migrator` identity.

## Prioritized improvements

### 1. Fix worker TLS configuration

**Reproduced finding:** a Scanner URL containing `sslrootcert` produces `unexpected keyword argument 'sslrootcert'`. The URL conversion leaves this option as an argument incompatible with the call to `asyncpg.connect`. Without an explicit TLS mode, the workers also do not enforce server certificate verification.

Momentum data access uses the same URL conversion pattern. The Scanner reader already builds an explicit TLS context.

**Action:** construct an `SSLContext` using the CA, require certificate and hostname verification for remote connections, and restrict connections without TLS to local development. Add tests for an invalid CA and an incorrect hostname.

Code: [Scanner URL conversion](../apps/backend/market-scanner-adk/src/app/services/database.py), [Momentum sessions](../apps/backend/momentum-adk/app/infrastructure/session_database.py), [Momentum runner](../apps/backend/momentum-adk/app/job_runner.py), [Scanner reader](../apps/backend/market-scanner-api/src/app/database.py).

Reference: [asyncpg TLS options](https://magicstack.github.io/asyncpg/current/_modules/asyncpg/connection.html).

### 2. Persist Momentum application memory

The Dockerfile places the decision log at `/tmp/momentum/memory.md`. The worker uses this file to prepare context and record decisions. Momentum's Terraform configuration does not attach persistent storage to that path.

SQL results persist, but this memory does not survive the Cloud Run instance stopping. It therefore cannot serve as shared memory across executions.

**Action:** store decisions, observed outcomes, and reflections in PostgreSQL, with an execution reference and user isolation. Define transaction consistency between result persistence and memory updates. Reserve `/tmp` for caches and temporary files.

Code: [Dockerfile](../apps/backend/momentum-adk/Dockerfile), [memory usage](../apps/backend/momentum-adk/app/job_runner.py), [current decision log](../apps/backend/momentum-adk/app/infrastructure/memory/log.py).

Reference: [Cloud Run filesystem lifecycle](https://docs.cloud.google.com/run/docs/container-contract).

### 3. Enforce database CI coverage and use the current migration entry point

At the audited revision, the Scanner workflow ran only unit tests, and `database/**` changes did not trigger it. PostgreSQL writer integration tests already existed. The reader workflow had its own PostgreSQL coverage, and Momentum already had a database job.

**Publication status:** the newer domain database workflow covers these paths and runs Scanner writer integrations through the rehearsal script. The original CI coverage gap is partially addressed; this report does not establish whether that check is required by branch protection.

At the original publication revision, the cross-domain harness selected `db.changelog-momentum.yaml`, which applies two changesets, while the entry point documented by the [Momentum guide](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/48ac681/database/MOMENTUM.md), `momentum.yaml`, applies three. The general database README and the Momentum guide also had inconsistent installation guidance. The implementation follow-up replaces these competing paths with one entry point per domain.

**Action:** retain the new PostgreSQL and Liquibase CI coverage, confirm that the relevant check gates merging, and align the harness and installation documentation with the supported migration entry point. Verify privileges and transactions using runtime identities, fail when the required test database is missing, and preserve already-applied changelog history.

Code: [Scanner workflow](../.github/workflows/scanner.yml), [writer integrations](../apps/backend/market-scanner-adk/src/test/integration/test_shared_database.py), [cross-domain harness](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/48ac681/database/scripts/local_domains.py), [Momentum entry point](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/48ac681/database/changelog/momentum.yaml).

### 4. Prove that data can be restored

The guides describe backup precautions, but no scheduled backup or automated restore exercise was found in the audited repository. This does not establish whether provider-managed backups exist.

**Action:** define the maximum acceptable data loss and recovery time, then schedule encrypted backups and periodic restores into an isolated target. Verify data, privileges, and Liquibase status after restoration. For LiteLLM, also preserve the original `salt-key`, which is required for encrypted records.

Confirm which recovery mechanism is available for the Aiven plan actually in use.

Code: [Momentum guide](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/48ac681/database/MOMENTUM.md), [LiteLLM recovery guide](../infra/litellm/RECOVERY.md).

References: [PostgreSQL backups](https://www.postgresql.org/docs/17/backup-dump.html), [Aiven restoration](https://aiven.io/docs/products/postgresql/howto/restore-backup).

### 5. Prevent duplicates when an execution is replayed

**Reproduced finding:** saving the same execution twice creates two Scanner reports and two Momentum results. Row identifiers are generated on each save; the tables do not enforce uniqueness of the logical execution.

The Scanner job already rejects some scheduled-session replays, but that protection does not guarantee storage-level idempotency.

**Action:** define a stable execution key, add a `UNIQUE` constraint, and handle conflicts explicitly within the transaction that writes the result and its children. Preserve the ability to perform several legitimate analyses of the same ticker on the same day: `(ticker, date)` is not a sufficient idempotency key.

Code: [Scanner persistence](../apps/backend/market-scanner-adk/src/app/services/market_scan_persistence.py), [Momentum results](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/48ac681/database/changelog/momentum-unified/results.sql), [Scanner job replay protection](../apps/backend/market-scanner-adk/src/app/jobs/daily_scan.py).

Reference: [PostgreSQL constraints](https://www.postgresql.org/docs/17/ddl-constraints.html).

### 6. Reduce LiteLLM runtime SQL privileges

The bootstrap makes `litellm` the owner of its database. The runtime and migration job use the same SQL credential secret. Separate GCP service accounts do not change the privileges of that PostgreSQL identity.

**Action:** evaluate separating the owner/migration identity from the runtime login, then verify LiteLLM operations and upgrades with that separation. An owner retains modification and deletion powers; disabling startup migrations does not remove those SQL privileges.

Code: [LiteLLM bootstrap](../infra/litellm/scripts/bootstrap_database.py), [secret configuration](../infra/litellm/foundation.tf), [migration job](../infra/litellm/migrations.tf).

Reference: [PostgreSQL privileges and ownership](https://www.postgresql.org/docs/17/ddl-priv.html).

### 7. Prepare for growth using measured improvements

At the audited revision, the eleven Momentum child tables had no index beginning with `result_id`. The later Aiven capture includes consultation indexes beginning with `result_id` on all eleven tables; these are retained in the new baseline. Scanner paginates using `(created_at, id)`, while its chronological index covers only `created_at`. The Momentum child-table index gap is addressed. Scanner pagination remains an optimization candidate; no production slowdown was measured during the audit.

**Action:** measure representative queries using `EXPLAIN (ANALYZE, BUFFERS)`, then add indexes supported by those measurements, including the remaining Scanner pagination candidate. Also review uniqueness constraints for relationships declared as one-to-one in the ORM.

Complete the operational setup with:

- Explicit retention for ADK sessions and events, separate from business-result retention.
- A global connection budget accounting for workers, concurrent jobs, deployments, and administrative access.
- Alerts for disk usage, connections, timeouts, analysis freshness, and backup age.
- A review of monetary columns: use `NUMERIC` and decimal values where exactness is required, retaining floating-point types for appropriate approximate measurements.

Code: [Momentum schema](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/48ac681/database/changelog/momentum-unified/results.sql), [Scanner schema](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/48ac681/database/changelog/market-scanner/001-analysis.sql), [Scanner pagination](../apps/backend/market-scanner-api/src/app/repositories/market_scan_repository.py).

References: [indexes and ordering](https://www.postgresql.org/docs/17/indexes-ordering.html), [PostgreSQL statistics](https://www.postgresql.org/docs/17/monitoring-stats.html), [numeric types](https://www.postgresql.org/docs/17/datatype-numeric.html).

## Audit verification results

| Verification | Result at the audited revision |
| --- | --- |
| Targeted Scanner tests | 21 passed, including 5 PostgreSQL integration tests |
| Targeted Momentum tests | 26 passed |
| Current Scanner migrations | Validation, update, and repeat update passed; 2 changesets and 8 business/session tables |
| Current Momentum migrations | Validation, update, and repeat update passed; 3 changesets and 17 business/session tables |
| Table ownership in both installations | `database_migrator` |
| CREATE/TEMP privileges for the three writer logins checked | Absent with the current bootstraps |
| Failure injected after a Momentum write | Transaction rolled back; no additional result persisted |
| Repeated save of the same execution | Duplicates reproduced in Scanner and Momentum |
| Scanner URL with an explicit CA option | `sslrootcert` incompatibility reproduced |

These targeted checks are not a full test-suite run or production validation. The audit changed no application code or remote databases. The PostgreSQL container created for verification was stopped and automatically removed. The implementation follow-up above distinguishes the completed reorganization from the remaining audit recommendations.
