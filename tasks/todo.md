# Momentum consultation execution checklist

Status: authorized implementation in an isolated worktree; no production rollout.
Paths below are relative to `apps/backend/momentum-api` unless qualified.
Each item has at most five implementation/test files; checkpoint evidence is
recorded in the delivery report and PR descriptions.

- [x] T01 Design baseline and isolated worktree.
  - Files: specs (2), plan, checklist; preserve prior worker files in archive.
  - Verify: links/format, fresh `origin/main`, clean scoped diff.
- [x] T02 Package, reader configuration and input contracts.
  - Files: pyproject.toml, uv.lock, src/app/config/settings.py, src/app/domain/analyses/search.py, src/test/unit/test_inputs.py.
  - Accept: safe reader URL/auth defaults; canonical ticker/rating; bound cursors.
  - Verify: focused pytest, Ruff, mypy.
- [x] T03 Typed summaries and financial detail projection.
  - Files: src/app/presentation/dto.py, src/app/domain/analyses/financial_sections.py, src/app/adapters/postgresql/mapper.py, src/test/unit/test_dto.py, src/test/fixtures.py.
  - Accept: source field/alias parity, finite values, no execution/user fields.
  - Verify: mapping and malformed-storage tests.
- [x] T04 Negotiation and conditional read policy.
  - Files: src/app/presentation/http/negotiation.py, src/app/presentation/http/conditional.py, src/app/presentation/http/problems.py, src/test/unit/test_http_policy.py.
  - Accept: q-values/wildcards, strong/weak ETags, stable typed errors.
  - Verify: focused protocol cases, Ruff and mypy.
- [x] T05 Authenticated HTTP lifecycle and liveness.
  - Files: src/app/presentation/http/middleware.py, src/app/app_factory.py, src/app/main.py, src/test/unit/test_application.py.
  - Accept: HEAD/OPTIONS/auth/challenges, no secret logs, engine lifecycle hook.
  - Verify: in-process full request matrix; storage not called for unauthorized input.
- [x] T06 Database permission foundation.
  - Files: database/momentum-reader-bootstrap.sql, database/changelog/momentum-reader.yaml, database/changelog/momentum-reader/001-reader.sql, scripts/test_database.sh.
  - Accept: isolated reader role/grants and safe disposable Liquibase harness.
  - Verify: migration validation/update/repeat on labelled local PostgreSQL.
- [x] T07 Storage connection and bounded history queries.
  - Files: src/app/adapters/postgresql/connection.py, src/app/adapters/postgresql/repository.py, src/app/services/analysis_service.py, src/test/integration/conftest.py, src/test/integration/test_history.py.
  - Accept: read-only lifecycle, deterministic history/cursors, sanitized SQL errors.
  - Verify: real database history/timeout/configuration tests.
- [x] T08 Detail/latest/recommendations and HTTP routes.
  - Files: src/app/presentation/routes/analyses.py, src/app/adapters/postgresql/repository.py, src/app/services/analysis_service.py, src/test/integration/test_analyses.py, src/test/unit/test_application.py.
  - Accept: all four use cases, ties, rating-after-latest and complete detail.
  - Verify: >100-row pagination and API field-preservation assertions.
- [x] T09 Effective privilege and writer compatibility verification.
  - Files: src/test/integration/test_permissions.py, scripts/check_storage_contract.py, src/test/unit/test_storage_contract.py.
  - Accept: writes/DDL/TEMP/cross-schema reads denied, projected columns exist.
  - Verify: real roles, worker model AST compatibility without runtime imports.
- [x] T10 Reusable API artifacts and documentation.
  - Files: scripts/export_openapi.py, openapi.json, README.md, docs/postman/momentum-api.postman_collection.json, .env.example.
  - Accept: deterministic contract, documented problems/commands, runnable requests.
  - Verify: OpenAPI drift check and collection assertions against local service.
- [x] T11 Production image and local runtime verification.
  - Files: Dockerfile, .dockerignore, scripts/container_smoke.py, src/test/unit/test_packaging.py.
  - Accept: non-root locked image boots and enforces real HTTP behavior.
  - Verify: Linux amd64 build, wheel build, container smoke and dependency audit.
- [x] T12 Dedicated Terraform root and validation.
  - Files: infra/momentum-api/main.tf, variables.tf, tests/reader.tftest.hcl, .terraform.lock.hcl, README.md.
  - Accept: private IAM, immutable inputs, bounded pool/replicas and isolated state.
  - Verify: fmt/init/validate/test, Linux/macOS provider checksums.
- [x] T13 CI and update automation.
  - Files: .github/workflows/momentum-api.yml, .github/dependabot.yml.
  - Accept: offline PR gates, mandatory PostgreSQL/coverage/image/contract/TF checks.
  - Verify: workflow inspection plus local equivalents and remote CI.
- [x] T14 Review and PR publication.
  - Files: scoped corrections and docs/specs/momentum-api-delivery.md evidence.
  - Accept: spec audit, no secrets, <=1,000 lines per PR, dependency links, no auto-merge.
  - Verify: published diffs/head SHAs/checks; live deployment explicitly separate.

Evidence: [delivery report](../docs/specs/momentum-api-delivery.md).
Implementation series: PR #111 through #132; final API and Terraform CI pass.
Production acceptance remains explicitly outside this implementation/MR delivery.

- [x] T15 Organize modules by responsibility.
  - Accept: domain, services, adapters and HTTP presentation are explicit packages.
  - Verify: original 106 unit tests, strict mypy and unchanged OpenAPI export.
- [x] T16 Enforce application boundaries and independent storage projections.
  - Accept: reader port returns domain models; services have no HTTP/storage imports;
    presentation owns public DTO mapping and status codes; SQL columns are explicit.
  - Verify: architecture/service regressions, independent financial golden fixtures,
    143 tests on fresh PostgreSQL, 97.07% coverage and 56 release-image Postman assertions.

- [x] T17 Apply operational engineering practices.
  - Accept: structured safe JSON diagnostics, upstream trace correlation only,
    preserved internal causes, injected test settings and primary-failure-safe cleanup.
  - Verify: 152 tests with real PostgreSQL, 97.14% coverage, real failing-handler
    regression and release-image JSON log/Request-ID checks plus 56 Postman assertions.
