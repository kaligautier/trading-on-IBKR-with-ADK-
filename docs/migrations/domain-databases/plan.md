# Plan: Fresh domain database rebuild

Status: local implementation and authorized remote cutover verified on 2026-10-21.
See the [checklist](todo.md), [local evidence](local-evidence.md),
and [remote evidence](evidence.md).
Source of truth: [rebuild specification](../../specs/database-per-application.md).
This replaces the previous copy/rollback/compatibility plan in full.

## Architecture

- `market_scanner` and `momentum` each have `_sessions`, `_analysis`, `liquibase`.
- Both Scanner and Momentum persist ADK sessions. Scanner also persists each
  successful scan's report and normalized rows, then serves them through its reader.
- Keep LiteLLM's native database/data. Keep the Aiven service and unrelated data.
- Fresh Liquibase chains create the final layout directly. Old domain data/history
  may be destroyed as authorized. Do not preserve old schemas/checksums or create
  copying, inverse migration, compatibility or delayed-cleanup machinery.
- Match ADK 2.6.1 session definitions and inspect the installed SDK's integration
  point for the Scanner server. Runtime roles perform DML only, never SDK DDL.
- New session pool: one connection, zero overflow per process. Include analysis
  pools, service replicas and concurrent jobs when calculating database role limits.
- A failed rebuild is repaired forward; destructive reset never runs automatically
  as a retry. Existing in-memory sessions cannot be migrated or recovered.

## Dependency order

```text
R0 current inventory + disposable harness
 ├─ R1 fresh Scanner/Momentum chains + scoped reset/bootstrap
 ├─ R2 Scanner session adapter → job + ADK server
 │    └─ analysis writer + read-only API proof
 └─ R3 Momentum session/analysis configuration
R1 + R2 + R3 → R4 exact release config + complete local rehearsal + CI
R4 → R5 stop old consumers → authorized reset/bootstrap → new deployment
R5 → R6 fresh Scanner run + restarted session/analysis verification + final audit
```

Each checklist task changes at most five files; application components get separate
PRs. Split before 1,000 counted changed lines. Code work can proceed independently
once schema contracts are fixed; shared SQL edits and live operations are serialized.

## Delivery and verification checkpoints

1. **R0:** identify all consumers, exact databases/legacy objects, role grants and
   current deployments. Resolve Momentum's authoritative foundation/deployment owner.
   Unknown objects are excluded until identified; no guesses about PUBLIC tables.
2. **R1:** build fresh schemas and test exact role rights on disposable PostgreSQL.
   Reset tooling validates expected host/service/database and explicit object scope.
   It excludes LiteLLM/system/unrelated objects, drains old consumers and refuses
   unexpected dependencies. Fresh history and repeated Liquibase update are tested.
3. **R2:** replace Scanner in-memory sessions in the scheduled job and interactive
   server. Use one adapter with schema preflight, bounded pool and explicit closure.
   Test restart, errors, repeated execution IDs and session/report correlation.
   Reader sees `_analysis` only; session deletion must not delete analyses.
4. **R3:** target Momentum `_sessions` with its existing adapter and `_analysis`
   for implemented results. Do not implement a new Momentum workflow or public API.
5. **R4:** freeze exact image digests, numeric connection-secret versions and schema
   settings. Test combined connection limits. Rehearse reset/bootstrap and both
   runtimes in separate processes with mocked external providers. No long observation
   window or old-data restoration is required in build mode.
6. **R5:** inspect final concrete targets, stop old consumers, perform the authorized
   domain reset/legacy cleanup, create schemas and grants, then deploy new releases.
   A failed phase leaves consumers stopped until repaired, not silently reset again.
7. **R6:** trigger the new Scanner run when runtime prerequisites are ready. Prove
   its durable session/events, report, API response and post-restart retrieval.
   Prove Momentum via a synthetic session round trip. Audit defaultdb and LiteLLM.

## Operational commands

Exact commands are in the [runbook](operations.md). Keep
credentials in protected configuration files, never argv/logs. The final runbook
must name the actual Cloud Run/Terraform deployment resources before execution.
User authorization already covers data loss for these application domains; a new
permission request is needed only if ownership or scope changes, not for each
routine reset step. The fresh paid-provider run remains an explicit recorded step.

## Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Reset hits unrelated storage | Expected service identity, explicit object allowlist and dependency validation. |
| ADK creates tables at runtime | Preflight exact pinned schema; real DDL-denial tests under runtime role. |
| Session loss still occurs in one entry point | Restart integration tests for both scheduled job and ADK server. |
| Added sessions exceed connection capacity | Measure both pools across runtime instances; set explicit role limits. |
| Repeated scheduled ID overwrites/replays work | Explicit tested completed/resume/reject behavior; no blind create/replay. |
| False success after partial persistence | Successful run requires both durable session and analysis, with correlation. |
| Legacy code still writes old schemas | Stop all identified consumers before reset; deploy final schema settings only. |

Completion requires direct evidence for DB-01 through DB-12 in the spec. Fresh
local tests, CI and live execution are recorded separately. The user approved implementation and subsequent remote execution; compatibility
and backup-recovery tasks are superseded.
