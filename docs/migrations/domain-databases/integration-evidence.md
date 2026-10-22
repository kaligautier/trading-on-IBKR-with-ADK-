# Integration with the merged Momentum implementation

Verified locally on 2026-10-22 against main revision `46e6927`, after integrating
the complete Momentum PR stack and the pinned PostgreSQL JDBC build correction.
This supplements the original local and remote evidence; no remote cutover was
repeated during PR integration.

The new Scanner analysis DDL is `market-scanner/001-analysis.sql`. The original
`001-initial.sql`, shared master and bootstrap remain historical fixtures for
Momentum migration-history regression tests. Runtime migration commands select
the independent domain roots explicitly. The Scanner checksum regression mutates
the new analysis file and still requires Liquibase to reject changed history.

`python3 database/scripts/rehearse_domains.py` passed with real local PostgreSQL:

| Suite | Passed |
| --- | ---: |
| Shared domain database, harness and cutover guards | 18 |
| Scanner unit and integration | 375 |
| Reader unit and integration | 38 |
| Momentum unit | 164 |
| Momentum adapter persistence | 8 |

The existing Momentum PostgreSQL workflow commands also passed all 52 integration
tests, including historical checksums, rollback, grants and database isolation.
The bootstrap itself grants every runtime role CONNECT; the local harness and
Scanner integration fixtures no longer add corrective grants. Cutover regression
tests require the desired Cloud Run generation to be reconciled and Ready, reject
a created revision that is not ready, and verify decoded passwords
for both asyncpg and Liquibase, including redaction in local evidence files.
Ruff and `git diff --check` passed. Provider calls remain simulated in the local
rehearsal; the earlier real Scanner execution is recorded in `evidence.md`.

The CI prerequisite scopes pinned LiteLLM image audits to gateway infrastructure
changes, explicit dispatches and daily scheduled runs. Scanner dependency audits
and gateway compatibility tests remain active for Scanner lockfile changes.
Seven real Git scenarios verified scope decisions, including a Scanner branch
whose base independently changed LiteLLM infrastructure. Scheduled runs have a
separate concurrency group. Existing gateway image findings remain blocking for
gateway changes and are not ignored or allowlisted.

The final rehearsal also uses OpenTelemetry API/SDK 1.45.1 for both applications.
Their runtime dependency audits pass, and an actual offline ADK tool round trip
exports seven valid SDK spans in each environment. The renamed Scanner SQL file
retains its deployed changeset logical path; applying the old physical-path
changelog followed by the new root preserves every history row and checksum.
