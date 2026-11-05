# REST versioning tasks

- [x] Record approved breaking-change spec and isolate component branches.
- [ ] M1 Suggestion submission outcome distinguishes created/existing atomically.
  Verify: repository integration and concurrency tests; domain, port, service, adapter.
- [ ] M2 Version routes and align status/Location/HTTP policy.
  Verify: failing then passing HTTP tests; routes, middleware, schema, HTTP tests.
- [ ] M3 Export OpenAPI and update docs; full Momentum API checks.
  Verify: export --check, Ruff, mypy, disposable PostgreSQL suite.
- [ ] S1 Version Scanner read routes and cover removed paths/HEAD/methods.
  Verify: route tests; router, factory, HTTP policy, route tests.
- [ ] S2 JSON negotiation and contract docs/smoke checks.
  Verify: representation cases, full Scanner API tests, lint/types.
- [ ] A1 Version job submission, 202 acknowledgement, admission rules.
  Verify: dispatch/auth/old-path tests; application, admission, existing tests.
- [ ] C1 Migrate public MCP gateway and maintained mocks/collections.
  Verify: gateway tests, local simulation, full MCP checks.
- [ ] C2 Migrate Momentum job client.
  Verify: real HTTP contract test and worker unit suite, Ruff.
- [ ] C3 Migrate frontend reader.
  Verify: reader tests, lint/typecheck/build and local provider integration.
- [ ] C4 Migrate Scheduler URI and operator docs.
  Verify: Terraform fmt/validate/test; schedule, assertions, README.
- [ ] I1 Combined candidate provider/consumer rehearsal.
  Verify: exact commits, real local HTTP paths and persistence; no live provider calls.
- [ ] P1 Eight scoped PRs open with passing applicable CI (two for Momentum API).
  Verify: diff scope/size, pushed SHAs, required checks, spec links/dependencies.
