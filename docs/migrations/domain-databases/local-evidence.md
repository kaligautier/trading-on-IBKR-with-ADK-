# Local domain rebuild evidence

Scope: the user approved implementation and local testing. All database mutations
in this work target disposable loopback containers. No remote database, secret,
Cloud Run service, image registry or LiteLLM deployment was changed here.

## Verified implementation

- Dedicated `market_scanner` and `momentum` databases on port 55461.
- Independent Liquibase histories and schemas `_sessions`, `_analysis`, `liquibase`.
- Scanner job and HTTP API use PostgreSQL ADK sessions, with schema preflight and
  bounded pools. No in-memory fallback. Sessions survive application/process restart.
- Scanner reports remain after session deletion. Replayed execution IDs fail
  explicitly. Failed persistence leaves the session and no successful job result.
- Reader serves the same stored report after recreation, cannot read sessions,
  and cannot write analyses. Runtime DDL and cross-database access are denied.

## Commands and results

`python3 database/scripts/rehearse_domains.py --momentum-root ../momentum-cloud-run`
passed locally: 7 foundation/harness, 374 Scanner, 38 reader, 133 current Momentum
unit tests and 7 current Momentum persistence/permission tests: **559 passed**. No tests were skipped. Providers/model responses are synthetic;
ADK, PostgreSQL, Liquibase, HTTP routing and role grants are real.

`docker build -t local/scanner-domain:verify apps/backend/market-scanner-adk`
and `python3 scripts/scanner_image_smoke.py local/scanner-domain:verify` passed.
The image test creates a session, restarts the actual container process and reads
its stored state, checks non-root packaging and fail-closed worker configuration.

Terraform `init -backend=false -lockfile=readonly`, `validate`, and mocked `test`
passed for `infra` (10 tests) and `infra/reader` (6 tests). No cloud apply occurred.
Scanner/reader lint and reader mypy passed. The new CI workflow is checked in;
GitHub CI has not been run or claimed green by this local work.

## Source revisions and remaining deployment work

Scanner session implementation: `7e046f7`; reader adaptation: `0a2aae9`.
Initial Momentum adapter validation used foundation `19641ad`, adapted as `c7072f7`.
A later local inventory found the more complete Momentum runtime at `e0cbd36`
in the `momentum-cloud-run` worktree. The final rehearsal uses that runtime and its
unchanged unified session/result migrations. Its dirty README and existing
containers were preserved. The earlier foundation-only adapter branch is superseded
for current Momentum validation; do not deploy it over the newer runtime.

Current Momentum tests use the real session adapter and result repository, writing
all twelve result tables, checking transaction rollback on three injected failures,
correlation with ADK events, session restart and separate role permissions. Deleting
a session leaves its analysis intact. No legacy Momentum migration is run locally.

Catalog inspection after the rehearsal lists `market_scanner`, `momentum`, and
`postgres`. The `postgres` database has none of `_sessions`, `_analysis`,
`market_scanner`, or `momentum` schemas. There is no local `defaultdb` database.

Remote inventory, consumer shutdown, remote reset, new connection-secret versions,
release images, rollout and a new live Scanner run remain outside this local apply.
Nothing here establishes the current contents of remote `defaultdb`. Existing
remote state described by other worktrees has not been independently reverified.
