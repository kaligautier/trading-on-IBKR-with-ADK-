# REST versioning implementation plan

User authorized immediate breaking changes on 2026-11-04. Spec:
[rest-api-versioning](../docs/specs/rest-api-versioning.md).
No compatibility aliases or repeated phase approvals. Existing task history is
preserved under tasks/archive/database-runtime-reliability-*.md.

1. Momentum provider in two dependent PRs to respect the 1000-line limit:
   version suggestion paths and OpenAPI, then 201 created / 200 existing with
   Location; preserve HTTP policy and test persistence.
2. Scanner ADK provider: POST /internal/v1/scan-jobs with 202; update admission;
   preserve SDK routes and test no dispatch through the removed route.
3. Scanner reader: version reads; HEAD, Allow and JSON negotiation; test old
   paths absent and auth/report/cursor behavior preserved.
4. Consumers in separate branches: public MCP, Momentum job, frontend, Scheduler.
   Update paths, expectations, saved fixtures and documentation in each scope.
5. Stack component PRs in this order; move the existing MCP/PostgreSQL smoke
   invocation to the consumer workflow (including provider/database path triggers)
   so it tests matching contracts, preserving the actual test.
6. Combined candidate integration: actual providers and consumers on local
   disposable data. No cloud or model execution. Publish eight scoped PRs and
   verify their exact-head CI results; no merge or deployment.

Dependencies: MCP requires Momentum and Scanner API; frontend and Momentum job
require Scanner API; Scheduler requires Scanner ADK. Providers and consumers
must be released together because old paths are removed. PR descriptions state
this dependency explicitly. Branches all originate at origin/main 8a4dbb8.

Risks: false 201 on deduplicated suggestions (test real concurrent inserts),
route-name-specific middleware (exercise full ASGI boundary), SDK route collision
(test auth/admission), drifted mocks (combined provider/consumer verification).

CI required targeted security patches in existing lockfile entries: joserfc
1.7.6 (Scanner ADK and MCP), pyasn1 0.6.5 (Scanner ADK and Momentum job).
No new package was introduced. Scanner ADK precedes Scanner API because the
reader CI also checks the ADK writer. Dependency audits and tests pass locally.
