# REST versioning delivery evidence

Date: 2026-11-05. Baseline: origin/main
`8a4dbb829e7f9d1477c8dd923e66724606d079dd`.
The original feat/ai-startup-vision checkout was preserved. Work uses isolated
worktrees, without stash. No merge, deployment, Terraform apply, live scan or
market-data/model call was performed.

## Target and review order

Project-owned business resources use /v1; removed paths have no aliases.
Health, readiness, documentation and SDK/MCP/LiteLLM protocol paths retain their
documented contracts. /v1 is a project convention, not a requirement of RFC 9205.

| Order | PR | Component | Candidate commit |
| --- | --- | --- | --- |
| 1 | [#261](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/261) | Momentum paths | c96d469 |
| 2 | [#262](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/262) | Momentum creation semantics | 84b802e |
| 3 | [#264](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/264) | Scanner ADK | 0892bf1 |
| 4 | [#263](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/263) | Scanner API | 04b5090 |
| 5 | [#265](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/265) | Public MCP | 709c2b7 |
| 6 | [#266](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/266) | Momentum job | c2eb42c |
| 7 | [#267](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/267) | Frontend | ce6d91b |
| 8 | [#268](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/268) | Scheduler and delivery evidence | bbe10f7 before this documentation |

Each PR targets its predecessor, keeping application scope at most one
component. Momentum uses two PRs to preserve the generated OpenAPI contract
within the 1000-line review limit. Retarget descendants after landing parents;
rerun checks on the resulting base/head combination. Providers and consumers
must release together because this is an explicitly authorized breaking change.

## Local verification

| Component | Evidence |
| --- | --- |
| Momentum API | 266 tests against real disposable PostgreSQL/Liquibase; 95.79% coverage; Ruff, mypy, storage contract and OpenAPI export checks. The paths-only slice has 210 unit tests. |
| Scanner API | 60 passed, one separately gated domain test skipped; 94.12% coverage; Ruff and mypy. Domain rehearsal is mandatory in CI. |
| Scanner ADK | 380 unit tests, including dispatch/auth/admission, old-path non-dispatch, 202 and method behavior; Ruff. |
| Public MCP | 74 tests; Ruff; Postman simulation: 12 requests, 45 assertions. |
| Momentum job | 196 unit tests; Ruff; canonical URL and no legacy fallback regression tests. |
| Frontend | 16 tests; lint, typecheck and production build. |
| Scheduler | Terraform fmt, init with committed lockfile, validate; 10 mocked-provider tests. |

New suggestion creation returns 201; existing/concurrent duplicates return 200.
Both Location values resolve to the canonical resource, including mounted apps.
Scanner GET/HEAD, Allow, Accept weights/exclusions and no-store are exercised.
Submission acceptance is 202 with the existing Cloud Run operation identifier.

## Combined local runtime evidence

- Actual MCP over HTTP to actual Momentum API and labelled PostgreSQL fixture:
  nine saved Postman requests and 33 assertions passed. An independent SQL read
  confirmed the pending suggestion was committed. The maintained
  momentum-api/scripts/mcp_smoke.py is invoked by the MCP CI workflow.
- Actual Scanner API with a labelled PostgreSQL fixture on loopback served the
  checked-in synthetic report-v3 fixture to the real MCP gateway, Momentum job
  tool and TypeScript frontend reader. All three consumed the report and
  preserved their empty-store behavior (MCP error, job error string, frontend
  null). HTTP probes verified HEAD metadata, 405/Allow, 406/Vary and old-path 404.
- Runtime source was unchanged by the later documentation and dependency-only
  commits. The patched dependency environments passed their unit suites again.
  The two owned local database containers and test HTTP processes were stopped.
- Local Cloud Run ingress emulation proves HTTP and persistence, not deployed IAM.
  Container and domain migration checks run separately in CI.

## CI dependency correction

The first CI audit found pre-existing vulnerable transitive dependencies:
joserfc 1.7.4 and pyasn1 0.6.4. Only the corresponding lock entries changed:
joserfc 1.7.6 in Scanner ADK/MCP, pyasn1 0.6.5 in Scanner ADK/Momentum job.
No new runtime package or direct dependency was added. All three local
pip-audit checks reported no known vulnerabilities after the patches.

CI status is recorded on each linked PR for its actual published head.
The database rehearsal runs on every PR; component tests, images, Terraform,
security, size and scope checks are distinct evidence from local tests.

At 10:36 UTC on 2026-11-05, all eight published candidate heads in the table
had successful applicable checks, with no failed or pending check. Publication
jobs were intentionally skipped on PRs. This delivery-documentation commit is
subsequently verified by the same checks on PR #268; its live check results are
the authoritative status for that final head.
