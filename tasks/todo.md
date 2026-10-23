# Database runtime reliability tasks

User authorized implementation after PR #178. Each slice has a focused check.

- [x] T01 Preserve prior tasks and record dependency plan.
  - Files: spec, plan, todo, archived plan and todo.
  - Verify: document links, git diff --check.
- [x] T02 Scanner TLS adapter and engine integration.
  - Files: services/postgres_tls.py, database.py, session_database.py, TLS unit test, existing URL tests.
  - Accept: verified context, sanitized URL, insecure remote rejection, local fixture support.
  - Verify: focused Scanner unit tests (RED then GREEN).
- [x] T03 Momentum TLS adapter and engine integration (depends T02 contract).
  - Files: infrastructure/postgres_tls.py, session_database.py, job_runner.py, worker tests, TLS unit test.
  - Accept: identical security policy for session/result engines.
  - Verify: focused Momentum tests.
- [x] T04 TLS infrastructure and real handshake fixture (depends T02/T03).
  - Split into worker-specific commits, each <=5 files.
  - Accept: pinned CA mount/access, valid and invalid certificate/hostname tests.
  - Verify: real local TLS PostgreSQL handshakes and Terraform mock assertions.
- [x] T05 Memory migration (depends T03).
  - Files: migration SQL, changelog, migration tests, fixture migration selection.
  - Accept: upgrade/fresh/repeat behavior; baseline unchanged; reader denied.
  - Verify: disposable Liquibase upgrade and privilege tests.
- [x] T06 Memory repository (depends T05).
  - Files: memory repository, memory DTOs, focused integration tests.
  - Accept: user isolation, bounded retrieval, stable IDs, idempotence/conflicts.
  - Verify: real SQL sequential/concurrent writes and transaction rollback.
- [x] T07 Memory workflow integration (depends T06).
  - Files: contracts, memory service, reflection integration, focused tests.
  - Accept: pending outcomes retain source identity; provider calls outside SQL transactions.
  - Verify: unit tests with deterministic outcomes/reflections.
- [x] T08 Atomic completion and restart behavior (depends T07).
  - Files: result repository, runner, execution service, Dockerfile, integration tests.
  - Accept: result/memory atomic; fresh process reads retained memory; no production file fallback.
  - Verify: rollback/failure and independent-process integration tests.
- [ ] T09 Capacity inventory and executable budget.
  - Files: budget manifest, verifier, verifier tests, deployment runbook.
  - Accept: reserved slots/consumers accounted; overbudget config rejected.
  - Verify: live read-only settings plus synthetic invalid configurations.
- [ ] T10 Scanner admission and pool alignment (depends T09).
  - Split runtime/database/infrastructure into <=5-file slices.
  - Accept: bounded concurrent execution and cleanup before model calls.
  - Verify: real simultaneous workers, cancellation and role/pool limits.
- [ ] T11 Momentum admission and shared consumers (depends T09/T08).
  - Split per component/configuration root into <=5-file slices.
  - Accept: memory adds no pool; aggregate limits cover release overlap.
  - Verify: concurrency and constrained-capacity tests including reader/LiteLLM simulations.
- [ ] T12 Full regression, review, packaging and PR publication.
  - Accept: every spec criterion mapped to direct evidence; local/live status explicit.
  - Verify: database rehearsal, lint, wheel, Terraform checks and each PR's required checks.

## Evidence so far

- Scanner TLS: 373 unit tests, six real TLS cases, ten Terraform tests; PR #179.
- Momentum TLS: 196 unit tests, combined 12 real TLS cases, three Terraform tests; PR #180.
- Memory schema: real additive upgrade retains session sentinel and prior Liquibase
  checksums; repeat update; seven private-memory privilege tests plus existing integrations.
- Memory repository: six real PostgreSQL tests cover concurrent retry, conflicting
  content, rollback, user isolation, distinct same-day IDs and bounded pending reads;
  196 existing Momentum unit tests remain green.
- Memory runtime: 227 unit/integration tests pass, including fresh-process recovery
  with empty home/tmp, result and memory rollback, and identical completion replay.
  Removed the file adapter and the Docker memory-path setting; no extra pool.
- Capacity inventory: max_connections=15, superuser_reserved_connections=3,
  reserved_connections=0; application/admin/migration budget must fit 12 ordinary slots.
