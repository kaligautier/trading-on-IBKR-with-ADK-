# Momentum consultation API delivery

Verified locally on 2026-10-22. Implementation tip: `fcad55dee47ccf8bea21d6797a04ef1f4e6a80ea`.
Rebased on main `7949165`. This report separates implementation evidence from
future production acceptance. No merge, registry publication, Terraform apply,
model execution or historical data import was performed.

## Delivered contract

The independent `apps/backend/momentum-api` exposes paginated history,
latest-per-ticker, UUID detail and recommendations under `/v1`. History contains
all retained runs; latest resolves equal timestamps by descending UUID, and
recommendations filter ratings after selecting the latest result. The service
reads only committed results and never dispatches analysis work.

Executable contract: [OpenAPI](../../apps/backend/momentum-api/openapi.json).
Operational commands, environment and stable problem types:
[service README](../../apps/backend/momentum-api/README.md).
[Product specification](momentum-consultation-api.md) and
[HTTP profile](momentum-http-rfc-profile.md) define the acceptance contract.

## Requirement evidence

Test paths below are relative to `apps/backend/momentum-api/src/test`.

| Spec criterion | Evidence and result |
| --- | --- |
| 1: operations and HTTP profile | unit/test_application.py, test_http_policy.py, test_openapi.py; all resource GET/HEAD/OPTIONS, authentication/challenges, negotiation, typed errors, conditional precedence, ETags and response metadata. Exact runtime/export equality. |
| 2: storage selection and pagination | integration/test_history.py and test_analyses.py: actual Liquibase tables, >100 results, timestamp ties, UUID winner, newer Sell excludes older Buy, filtered cursors, winner movement between pages, empty and unknown results. |
| 3: financial fidelity and privacy | integration/test_financial_fidelity.py and independent frozen financial_fixture.py: every exposed financial field/alias, both populated and null cases, child ordering, no internal correlation fields. Static writer AST contract and explicit projected columns detect storage drift. |
| 4: effective permissions and failures | integration/test_permissions.py, test_query_bounds.py and test_history.py: actual reader denied DML/DDL/TEMP/cross-schema reads even with read-only disabled; PUBLIC/direct column privileges and grant options rejected; timeout/schema/column failures sanitized; connection released. |
| 5: production package | Linux amd64 image boots as UID 10001; container_smoke.py exercises actual PostgreSQL, auth, exact OpenAPI, HEAD Content-Length, bodyless 304 and saved Postman requests. Independent wheel and sdist build. |
| 6: coverage | Fresh labelled PostgreSQL fixture: 132 passed, no skips, 96.83% combined line/branch coverage; required threshold 90%. |
| 7: infrastructure | Dedicated private IAM service/state/account, digest-only image and numeric secrets; Terraform fmt/validate plus six tests pass. No apply. |
| 8: live acceptance | Pending deployment authorization and provisioned reader secrets/IAM. No claim of live TLS, edge IAM or production data parity. |
| 9: PR policy | One commit and at most 884 counted lines per implementation PR; only uv.lock/package-lock.json excluded. One application component; base/head/dependency verification recorded with publication. |
| 10: reproducibility | Commands below, reusable local Postman collection, CI workflow, this report and explicit rollout prerequisites. Future MCP implementation is outside scope. |

## Reproduced commands and results

From `apps/backend/momentum-api`:

```sh
uv sync --frozen --python 3.12
uv run --frozen ruff check src scripts
uv run --frozen ruff format --check src scripts
uv run --frozen mypy src/app
uv run --frozen python scripts/check_storage_contract.py
uv run --frozen python scripts/export_openapi.py --check
uvx --python 3.12 --from openapi-spec-validator==0.7.2 openapi-spec-validator openapi.json
bash scripts/test_database.sh verify --cov=app --cov-branch --cov-fail-under=90 -q
uv build --out-dir dist
bash scripts/test_database.sh start
docker build --platform linux/amd64 --tag local/momentum-api:verify .
uv run --frozen python scripts/container_smoke.py local/momentum-api:verify
bash scripts/test_database.sh stop
```

Ruff passes; strict mypy passes for 17 source files. OpenAPI validates and matches
the executable contract. Liquibase validates, applies four changesets and repeats
with zero pending changes; all 132 tests pass. The fixture cleanup is also checked
on pytest failure and refuses to remove containers owned by another invocation.
Run database tests and image smoke sequentially: both own synthetic fixture data.
One upstream Starlette TestClient/httpx deprecation warning remains; it does not
change runtime HTTP behavior.

The release-image smoke passes 15 requests and 56 Postman assertions without cloud
publication. The independently pinned Postman Linux CLI is 1.73.0, archive SHA-256
`8f95dfcfc113a7af796783f88e19de26cc7606c9438b414e8cc485199b205817`.
The macOS Postman spec-lint command crashes in system credential handling; it is
not recorded as a passed lint. Independent OpenAPI validation and actual request
assertions provide the contract evidence instead.

Runtime dependencies: locked 19-package production environment; pip-audit 2.10.1
reported no known vulnerabilities. This is distinct from repository-wide default
branch advisories. The Dockerfile pins Python and uv image digests. The tested
local image manifest is
`sha256:8616a94aa2ca0f104595f5262d091274811e9d24672617d4e593e0fb38b85f81`;
this is a local verification artifact, not a registry release digest.

From repository root:

```sh
python3 -m unittest discover -s .github/scripts -p 'test_pr_*.py' -q
terraform -chdir=infra/momentum-api fmt -check -recursive
terraform -chdir=infra/momentum-api init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/momentum-api validate
terraform -chdir=infra/momentum-api test
git diff --check
```

Twenty PR-policy tests and six Terraform tests pass. Terraform provider checksums
cover darwin_arm64 and linux_amd64. No infrastructure was applied.

Summary storage uses five bounded SELECTs for either one or 100 page items.
A synthetic 10,000-result/1,000-ticker PostgreSQL 17 plan used the history index;
full latest-catalogue selection legitimately scanned/sorted the catalogue.
Observed local execution times were approximately 0.028 ms and 7.26 ms,
respectively; these are diagnostics, not a production latency SLO.

## Review and provenance

DeepCopy extraction baseline: `38d0736a4bf778ebcb81dbf4acef52fd2dd34e77`.
The independent legacy mapping fixture freezes source field names and aliases;
no sibling runtime import or copied migration history is introduced. The original
dirty checkout and DeepCopy source were preserved.

Independent review found Bearer whitespace/list grammar, public error identity,
request correlation and column-level privilege gaps. Each was corrected with
regression coverage. The final review reports no remaining Required/Critical
finding in those corrections. Human review remains required before merging.

## Dependency-ordered implementation PRs

Review each PR against its named base. Merge in order and retarget the next PR to
main after its predecessor merges; do not merge a descendant directly into main
while its dependencies remain unmerged. Intermediate slices are not releases.
The generated OpenAPI is published in readable additive slices; only the final
assembled artifact is complete and validated. No generated-file policy exemption
or minification was used.

| Order | PR | Change | Counted lines |
| --- | --- | --- | --- |
| 1 | [#111](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/111) | define consultation contract and delivery checks | 838 |
| 2 | [#112](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/112) | validate reader configuration and bound pagination inputs | 373 |
| 3 | [#113](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/113) | preserve typed financial response fields | 540 |
| 4 | [#114](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/114) | define HTTP negotiation and conditional semantics | 244 |
| 5 | [#115](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/115) | enforce authenticated HTTP response lifecycle | 370 |
| 6 | [#116](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/116) | isolate reader grants and consultation indexes | 145 |
| 7 | [#117](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/117) | read bounded history from isolated PostgreSQL role | 321 |
| 8 | [#118](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/118) | expose history latest detail and recommendations | 333 |
| 9 | [#119](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/119) | prove financial fidelity and effective reader isolation | 456 |
| 10 | [#120](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/120) | document HTTP policy and liveness OpenAPI | 831 |
| 11 | [#121](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/121) | publish technical and fundamental schemas | 729 |
| 12 | [#122](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/122) | publish summary and decision schemas | 610 |
| 13 | [#123](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/123) | publish supporting report and detail schemas | 480 |
| 14 | [#124](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/124) | publish readiness and authenticated documentation | 698 |
| 15 | [#125](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/125) | publish history and latest list contracts | 884 |
| 16 | [#126](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/126) | publish detail and recommendations contracts | 824 |
| 17 | [#127](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/127) | add operational guide and reusable consultation requests | 717 |
| 18 | [#128](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/128) | verify non-root image with real storage and Postman | 171 |
| 19 | [#129](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/129) | honor RFC list grammar and public error codes | 121 |
| 20 | [#130](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/130) | provision private IAM reader service | 323 |
| 21 | [#131](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/131) | gate reader contract storage image and infrastructure | 114 |
| 22 | [#132](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/132) | verify complete reader fidelity and privilege boundaries | 334 |

The implementation CI is attached to [#132](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/pull/132); the new workflow
is [Momentum consultation API](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/actions/runs/39841959990).
Remote workflow 39841959990 completed successfully: both API and infrastructure
jobs passed on the implementation tip. Its API job runs fresh Liquibase/PostgreSQL
tests, coverage, independent OpenAPI validation, the release-image Postman suite
and runtime dependency audit. PR size and component-scope checks also pass.
The earlier full workflow on #131 (39841949836) passed independently.
All checks on all 22 implementation PRs are terminal and green (or explicitly
skipped where inapplicable), including size, component scope and GitGuardian.
Scanner consultation, Momentum checks and domain database rehearsal on #132 pass.
Remote bases and head SHAs match the local series; each PR has exactly one commit.

## Before production acceptance

1. Review and merge the dependency series; publish the approved image by digest.
2. Provision the dedicated reader login/secret and verified PostgreSQL CA; review
   effective grants, run reader bootstrap and additive Liquibase reader migration.
3. Review Terraform plan in its isolated state with explicit authorized caller
   service accounts and immutable secret versions; apply only when authorized.
4. Verify TLS/certificate/negotiated HTTP protocol at managed ingress and database;
   prove anonymous and unauthorized identities denied and allowed identity accepted.
5. Compare a known retained analysis with an independent storage read, including
   exposed financial values; verify no writer, model or job activity from reads.

Cloud Run errors can precede the application's Problem Details contract. Record
those edge responses separately. No blanket transport/RFC certification follows
from the application tests or this report.

## Architecture follow-up

The package now separates `domain/analyses`, `ports`, `services`,
`adapters/postgresql` and `presentation`. The composition root remains
`app.main:create_app`. Domain read models are mapped into explicit public DTOs;
services use only the reader port and domain types. Domain failures receive HTTP
statuses only at the presentation boundary. SQL projections are explicit and do
not inspect response model fields. Unexpected failures retain only safe correlated
code-location diagnostics, without exception messages or local values.

Verification after the refactor: 143 tests pass against fresh Liquibase/PostgreSQL,
with 97.07% combined coverage. Ruff and strict mypy pass for all 33 runtime modules;
the exported OpenAPI is byte-for-byte unchanged. Architecture tests cover import
direction; service tests exercise pagination through a fake port and HTTP failure
mapping; independent financial fixtures also traverse the presentation mappers.
Wheel, source distribution and Linux amd64 release image build successfully.
The non-root release-image smoke passes all 15 Postman requests and 56 assertions,
including exact runtime OpenAPI, authentication, real storage, HEAD and 304.
The initial delivery evidence above describes the original tip; these checks
validate the subsequent architecture refinement. No endpoint, dependency, schema,
authentication policy or deployment change is introduced.
