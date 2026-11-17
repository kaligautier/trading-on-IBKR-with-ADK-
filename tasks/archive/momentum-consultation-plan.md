# Momentum consultation implementation plan

Authorized by the 2026-10-22 implementation/MR request. Scope follows
[the product spec](../docs/specs/momentum-consultation-api.md) and
[the HTTP profile](../docs/specs/momentum-http-rfc-profile.md).
The old worker plan/checklist are preserved under `tasks/archive/momentum-worker-*`.

## Architecture and delivery

A standalone Python 3.12 FastAPI reader uses the existing `momentum._analysis`
contract. Explicit Pydantic DTOs expose only the reviewed financial projection.
Parameterized SQL queries return bounded summaries and one complete detail;
HTTP policy owns authentication, negotiation, conditional reads and problem details.
There are no sibling imports, ADK/model calls, database writes or job dispatch.

Dependency order: contracts/configuration -> private liveness HTTP -> database
reader/grants -> history/detail -> latest/recommendations -> contract artifacts
-> image/CI/Terraform -> full verification and review. Database and runtime checks
use synthetic fixtures and an isolated labelled PostgreSQL server.

Each independently checked commit becomes a dependent PR under 1,000 counted
lines and affecting only the new application component. Generated OpenAPI changes
are reviewed in the corresponding contract slices; never weaken size checks or
compress source to evade them. First PR contains design; later PRs depend on it.
Only the final service is releasable. No merge, deployment or paid analysis occurs.

## Decisions

- Preserve DeepCopy field names/aliases, but declare nested schemas explicitly.
- Use the existing database/migration history; add a separate reader bootstrap and
  reader-only changelog so existing worker migration counts/checksums stay intact.
- Bound cursors to view and normalized filters; query latest-per-ticker before
  applying ratings/cursor. An older Buy cannot outlive a newer Sell in discovery.
- Enforce RFC HTTP semantics at an ASGI boundary; no streaming report endpoint is
  needed. HEAD and ETags operate on the same deterministic representation bytes.
- Default local authentication is opaque bearer; Cloud Run IAM mode requires the
  managed ingress. Problem types use the owned repository documentation URL so
  they are stable and reviewable without adding a public application endpoint.
- Choose dependency versions from the existing Scanner lock where compatible;
  generate the new lock and audit runtime dependencies before delivery.
- Main acceptance is locally reproducible source, tests, image and Terraform plus
  published PRs. Live deployment criteria stay explicitly pending in the report.

## Checkpoints

1. Contracts/HTTP: focused negative tests, Ruff and mypy; no runnable storage path
   until the repository is wired.
2. Real storage: actual Liquibase migrations, fixture round-trip, permission
   denials, tied timestamps and >100 results across all list views.
3. Delivery: all tests with >=90% branch-inclusive coverage, deterministic OpenAPI,
   Postman assertions against the real local service, production image smoke,
   dependency audit, Terraform fmt/init/validate/test and PR policies.
4. Review: inspect requirements against evidence, fix findings, publish the complete
   dependent PR series and verify remote head/check status.

## Risks

- RFC middleware can mishandle HEAD/304, Accept precedence or auth failures:
  explicit protocol tests precede implementation and run against the container.
- Data/ORM drift can leak or drop fields: explicit projection plus synthetic
  all-field fixtures and a static writer-column compatibility check.
- Effective PUBLIC/inherited privileges can bypass nominal read-only grants:
  real negative permission tests with a non-owner role and bootstrap validation.
- Production identity/TLS are outside unit-test proof: no deployed-conformance
  claim until separate live checks are authorized and performed.
