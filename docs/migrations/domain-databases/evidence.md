# Remote domain cutover evidence — 2026-10-21

The user authorized remote application after the local rehearsal and explicitly
accepted discarding old Scanner/Momentum application data. The final implementation
uses one database per application with `_sessions`, `_analysis`, and `liquibase`.
No data-copy or compatibility layer was added. Worktree: `database-per-app`, branch
`deploy/scanner-domain-database`. [Release map](release-map.md), [runbook](operations.md).

## Applied remotely

- Matched deployed connection hosts to Aiven `deep-copy/pg-25f92602`, PostgreSQL
  18.6, max connections 15. Inventoried all three Scanner consumers, Momentum,
  LiteLLM, legacy tables/history and active executions before mutations.
- Created `market_scanner`, applied non-superuser administrator/migrator bootstrap,
  validated and applied its two Liquibase changesets, then ran a no-op update.
  `_sessions`: five ADK 2.6.1 tables; `_analysis`: three report tables. Each domain
  owns an independent `liquibase` history; runtimes never migrate tables.
- Preserved existing Momentum database and current twelve-table analysis model.
  Its two migration IDs/checksums match the preflight inventory. Existing analyses
  remain; concurrent Momentum work continued independently.
- Published both tested linux/amd64 images and DB secret versions `2`, preserving
  deployed passwords/TLS parameters. Applied saved Terraform plans: two runtime
  updates and one reader update, no additions/deletions or unrelated changes.
- Verified both services ready at 100% traffic and the job uses the same Scanner
  digest and new database. Paused scheduling during cutover; no old job was active.
- Removed exactly the old Scanner's three tables (18 reports, 450 assets, 3438
  horizon rows), `market_scanner` schema, and isolated legacy Liquibase history
  from `defaultdb`. Drops used RESTRICT; unknown dependencies would abort.
- Removed PUBLIC-derived defaultdb CONNECT for Scanner/Momentum runtimes while
  explicitly preserving prior unrelated/operator login access. Final catalog:
  **zero application tables in defaultdb**, no Scanner/Momentum schema. Every
  Scanner/Momentum runtime has CONNECT only to its own domain among defaultdb,
  market_scanner, momentum and litellm.
- Scheduler `market-scanner-daily-0700` is ENABLED, `0 7 * * *`, Europe/Paris.
  Final Terraform detailed-exitcode plans for both roots returned **0: no changes**.
  Momentum job and LiteLLM gateway specifications match the original inventory.

## Durable live execution

First execution `market-scanner-daily-8jvwf` failed on a provider ReadTimeout after
180 seconds; gateway request evidence shows a later 200 response at ~213 seconds.
Its partial session/events remain. No schema reset or fabricated report was used
as recovery; no model timeout/provider configuration was changed.

New execution **`market-scanner-daily-v7ll2`** completed successfully, exit 0,
at `2026-10-21T16:04:21Z` (Cloud Run duration 4m4.88s).

| Proof | Observed value |
| --- | --- |
| Stored report | `727b7d90-042f-4513-8d1d-8b567da92c91` |
| Report session marker | `scheduled:market-scanner-daily-v7ll2` |
| ADK events for successful execution | 12 |
| Normalized assets / horizon rows | 25 / 191 |
| Reader latest + report-ID endpoints | Payload exactly equals stored report JSON |
| Session after worker process exit | Read through authenticated deployed ADK HTTP API, all 12 events |
| Interactive HTTP-created session | `cutover-http-20261021`, independently found in PostgreSQL |
| Scanner SDK close/reopen | State and event preserved, migration-verifier session |
| Momentum actual SDK close/reopen | `database-cutover-verifier-c825ea128efb46a6a16d82518c66c1ae`, state + event preserved |

The completed worker process exited before session/report retrieval from separate
Cloud Run services. Actual interactive container restart was also verified locally;
this run did not force a remote HTTP service restart. Final Scanner inventory:
four sessions, twenty events, one analysis (includes explicit verification sessions
and the failed scan). API health alone was not used as acceptance evidence.

## Tests and requirement audit

[Local evidence](local-evidence.md): 559 tests, actual Scanner container restart,
reader image smoke, Terraform mocked tests (10 + 6), Ruff and reader mypy passed.
The deployed linux/amd64 builds separately passed both image smoke tests. Current
cutover safeguards: six focused tests pass; reproducible PostgreSQL bootstrap test
passes as a non-superuser, including wrong-target refusal, no runtime DDL,
separate migrator ownership and preserved operator access during CONNECT retirement.
The remote PostgreSQL 18.6 verification supplements the local PostgreSQL 17 suite.

| Requirements | Authoritative evidence |
| --- | --- |
| DB-01 | Preflight service/database/object inventory; exact release map and preserved service specs. |
| DB-02 | Separate real catalogs and migration histories; Scanner second update no-op; Momentum existing history unchanged, fresh chain tested locally. |
| DB-03 | Live runtime CREATE/metadata UPDATE and reader session SELECT/analysis DELETE rejected; final effective CONNECT matrix isolated; local role tests. |
| DB-04 | Local actual container restart; remote SDK reopen; deployed HTTP-created session and post-worker-exit session read. |
| DB-05 | Successful execution correlated with stored report and normalized rows; separate reader returns exact report-v3 JSON after worker exit. |
| DB-06 | Current Momentum SDK synthetic round trip on remote database; five session and twelve implemented analysis tables; local result persistence tests. |
| DB-07 | Local session deletion keeps report; repeated IDs, storage failures and transactional result failures tested; failed live scan remains diagnosable. |
| DB-08 | Bounded runtime pools, inspected role limits and max instances; serialized jobs/rollout; engine-close tests and worker exit. |
| DB-09 | Wrong-target/foreign-container/credential-permission tests; Aiven host match; exact cleanup allowlist, RESTRICT transaction and verified successful run prerequisite. |
| DB-10 | Live image, schema, pinned secret and traffic checks for all consumers; both final Terraform plans empty. |
| DB-11 | Final defaultdb table inventory empty; domain CONNECT withdrawn; Momentum history and LiteLLM deployment preserved. |
| DB-12 | Real successful scan, persisted session/report and authenticated retrieval; local/remote/CI evidence distinguished. |

CI workflow is committed in the preceding implementation; it was not run on GitHub
in this session, so no green remote CI claim is made. Protected raw evidence lives
under ignored `.local/remote-domains/`; credentials/token are mode 0600 and excluded
from Git. The commands and non-secret conclusions above are reviewable artifacts.
