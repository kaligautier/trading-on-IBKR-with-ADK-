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
  - Delivered in worker-specific PRs; one commit per PR as requested.
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
- [x] T09 Capacity inventory and executable budget.
  - Files: budget manifest, verifier, verifier tests, deployment runbook.
  - Accept: reserved slots/consumers accounted; overbudget config rejected.
  - Verify: live read-only settings plus synthetic invalid configurations.
- [x] T10 Scanner admission and pool alignment (depends T09).
  - Delivered in a focused Scanner PR with one commit.
  - Accept: bounded concurrent execution and cleanup before model calls.
  - Verify: real simultaneous workers, cancellation and role/pool limits.
- [x] T11 Momentum admission and shared consumers (depends T09/T08).
  - Delivered in component-scoped PRs with one commit each.
  - Accept: memory adds no pool; aggregate limits cover release overlap.
  - Verify: concurrency and constrained-capacity tests including reader/LiteLLM simulations.
- [x] T12 Full regression, review, packaging and PR publication.
  - Accept: every spec criterion mapped to direct evidence; local/live status explicit.
  - Verify: database rehearsal, lint, wheel, Terraform checks and each PR's required checks.

## Verification evidence (2026-10-23)

The final combined tree passed `python3 database/testing/rehearse.py`: 900 tests
(66 shared database, 391 Scanner, 39 Scanner API, 193 Momentum unit,
37 Momentum PostgreSQL integration, 174 Momentum API). Shared tests include
verified TLS handshakes for both workers, bad CA/hostname rejection,
independent-process lock ownership/cancellation/crash cleanup, and concurrent
worker/reader/LiteLLM client simulations on PostgreSQL capped at 15 connections.
The capacity verifier reports 10 application + 1 migration + 1 operator slots,
with 3 additional PostgreSQL-reserved slots. Memory tests cover atomic rollback,
user isolation, bounded context, identical/conflicting replay, and a fresh process.

Delivery: #189 Scanner TLS, #187 Scanner admission, #192 Momentum TLS/memory
foundation, #188 Momentum runtime memory/admission, #190 complete shared budget.
Earlier PRs merged into intermediate branches did not deliver their code to main;
the final PRs restore those changes directly, preserving newer settings metadata.

This is code and local/CI evidence, not a production rollout. Migration, verified
TLS secret cutover, role-cap application and drain-before-replace deployment remain
operator steps. The live capacity gate requires full provider/client visibility;
a low-privilege snapshot cannot establish that headroom.

The unchanged upstream LiteLLM image pins trigger the image-security audit
(aiohttp, certifi, opentelemetry-api and pypdf findings). This is a separate existing
image remediation requirement; the connection-pool change does not change images
or suppress that audit. LiteLLM configuration and container checks pass.
