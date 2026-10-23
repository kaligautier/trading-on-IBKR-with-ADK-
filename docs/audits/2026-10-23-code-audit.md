# Code audit — October 23, 2026

Audited revision: `80e471486a4e1115baf68e6a1cef63e3d236dfed` (`main` at audit time).

> Historical snapshot: this report records evidence collected against the revision
> above. The PR publishing it is based on a newer `main`. Finding status and test
> results have not been revalidated against that newer revision. Source links are
> pinned to the audited commit so subsequent fixes and file moves do not change
> the evidence being reviewed.

**Verdict at the audited revision: changes required before another release.**
The audit identified one P1 and eleven P2 findings. Existing functional tests passed
but did not cover these defects. This document introduces no application changes.

## Scope and method

Reviewed the three Python services, Next.js frontend, PostgreSQL migrations and
scripts, Terraform roots, LiteLLM gateway, Dockerfiles, GitHub workflows, and their
contracts and documentation. Review axes: correctness, security, architecture,
readability, performance, and verification.

Applied `using-agent-skills`, `code-review-and-quality`, `security-and-hardening`,
`postman:api-engineer` / `api-testing`, and `browser-testing-with-devtools`.
Independent component reviews were consolidated with reproducible evidence.
Provider and LLM responses used in reproductions were synthetic.

Reviewed trust boundaries: visitor → frontend → private reader → PostgreSQL;
trigger → ADK workflow → providers / LLM → reports and sessions; application
identities → gateway → proxy; administrator → governance / secrets. Provider and
LLM output were treated as untrusted input.

The audit preserved pre-existing local work and made no cloud changes. Terraform
applies used for verification targeted only a disposable local LiteLLM instance.
TLS and CI observations from a separate local database report were independently
checked against source and dedicated probes before inclusion.

## Findings

### A01 — P1 — Pinned LiteLLM images contain vulnerable dependencies

Source: [variables.tf:54](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/infra/litellm/variables.tf#L54).
Installed Python distributions were inventoried inside both official images **by
digest**, on `linux/amd64`, with container networking disabled. Their package lists
were then checked using `pip-audit==2.10.1`.

| Image | Digest | Inventoried packages | Advisories / affected packages |
| --- | --- | ---: | --- |
| Proxy | `sha256:8a372e5c22acddcd78e86a68e1c054bd97768ae600006a776475d2d8d4e7574b` | 201 | 18 / 4 |
| Migrations | `sha256:6206b0d6832242a5dd5b3eb7542da64e7a5b06c80a60dfed6c20f8be0e359158` | 147 | 10 / 3 |

Both images installed `aiohttp 3.14.3` (eight advisories), `certifi 2026.4.22`, and
`opentelemetry-api 1.28.0`. The proxy also installed `pypdf 6.19.0` (eight advisories).
Counts overlap between images; they do not represent 28 distinct vulnerabilities.
The repository's image-security check failed.

The [Certifi advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2)
concerns trust in a compromised certificate root. The
[OpenTelemetry advisory](https://github.com/open-telemetry/opentelemetry-python/security/advisories/GHSA-xcq7-p3pf-p88h)
describes denial of service through `tracestate` parsing. Exploitability of every
advisory through the gateway was not demonstrated. Packages installed in a
migration image are not necessarily executed during migrations. The confirmed
finding is the affected installed versions and failed release gate, despite clean
application Python lockfile audits.

**Remedy:** select corrected official images for both roles, audit their installed
packages, update both digests, and rerun the smokes. No image replacement or advisory
exception was applied during the audit.

### A02 — P2 — Alpha Vantage credentials leak through errors

Sources: [common.py:76](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/momentum-adk/app/infrastructure/market_data/alpha_vantage/common.py#L76)
and [indicator.py:242](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/momentum-adk/app/infrastructure/market_data/alpha_vantage/indicator.py#L242).
The request puts `apikey` in the URL. The exception from `raise_for_status()`
contains that URL, and the handler prints and returns the complete exception.

**Evidence:** a synthetic HTTP 403 containing a sentinel key exposed the sentinel
in stdout and the tool result. That result can enter LLM exchanges and persisted
ADK events. No real credential was used. This affects installations configuring
Alpha Vantage; the audited Momentum Terraform did not inject that credential.

**Remedy:** return sanitized domain errors without provider URLs or exception
text. Assert that the sentinel is absent from logs, tool results, and events.

### A03 — P2 — Synchronous provider calls block the asyncio event loop

Sources: [Scanner agent.py:82](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/market-scanner-adk/src/app/components/agents/market_scanner/agent.py#L82),
[Momentum market_data.py:11](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/momentum-adk/app/components/tools/market_data.py#L11),
and [Alpha common.py:76](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/momentum-adk/app/infrastructure/market_data/alpha_vantage/common.py#L76).
The installed ADK SDK invokes these synchronous functions directly on its event
loop. Scanner collection makes 25 sequential provider calls. Momentum tools also
perform network calls and retries using `time.sleep`. Alpha has no HTTP timeout.

**Evidence:** a real Scanner workflow with a simulated 300 ms collection delayed
a concurrent coroutine by 313 ms. Two real Momentum tools simulating 150 ms of
network work each took 312 ms through `asyncio.gather`. On the single-worker
Scanner server, other requests and health checks can wait for collection to finish.
Parallel ADK branches therefore do not guarantee concurrent provider execution.

**Remedy:** expose asynchronous boundaries, offload synchronous clients through
`asyncio.to_thread`, set network deadlines, and bound concurrency. Test HTTP
responsiveness during slow collection and recovery after timeouts.

### A04 — P2 — Decimal debt values produce incorrect percentiles

Source: [market_data_trend_service.py:145](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/market-scanner-adk/src/app/services/market_data_trend_service.py#L145).
Only the current value is converted to `float`; reference values remain `Decimal`.
Binary rounding breaks equality comparisons used to calculate the midrank.

**Evidence:** 401 identical `Decimal("40047726949770.15")` values produced a 0th
percentile; the same values ending in `.10` produced the 100th percentile. With
400 equal reference values, both should produce the 50th percentile. The incorrect
result feeds the analysis.

**Remedy:** preserve the current value's numeric type when ranking it. Cover
Decimal ties and adjacent values in regression tests.

### A05 — P2 — Momentum indicators exclude the current trading session

Source: [stockstats.py:71](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/momentum-adk/app/infrastructure/market_data/stockstats.py#L71).
The download uses today's date as `end`, which is exclusive in the locked yfinance
version. The current session is excluded even after market close, and the day's
cache preserves that omission.

**Evidence:** a synthetic provider containing the October 23 session and honoring
the exclusive boundary yielded
`2026-10-23: N/A: Not a trading day (weekend or holiday)`.
Missing prices were incorrectly described as a non-trading day.

**Remedy:** correct the exclusive boundary and cache freshness policy. Distinguish
unavailable data, an ongoing session, and a non-trading day.

### A06 — P2 — Historical analyses can receive future insider transactions

Sources: [market_data.py:103](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/momentum-adk/app/components/tools/market_data.py#L103)
and [finance.py:422](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/momentum-adk/app/infrastructure/market_data/yahoo/finance.py#L422).
Momentum's contract includes an analysis date, but this tool takes only a ticker
and returns all currently available transactions.

**Evidence:** a synthetic October 22 transaction was returned with no way for a
caller analyzing an earlier date to impose its cutoff. This introduces look-ahead
bias into historical analyses.

**Remedy:** propagate the analysis date and filter by information availability,
or mark this source unavailable for historical analyses.

### A07 — P2 — Alpha indicator rate limits bypass the Yahoo fallback

Sources: [indicator.py:242](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/momentum-adk/app/infrastructure/market_data/alpha_vantage/indicator.py#L242)
and [router.py:153](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/momentum-adk/app/infrastructure/market_data/router.py#L153).
The router changes providers on `AlphaVantageRateLimitError`, but the first
provider catches that exception and returns an error string as its result.

**Evidence:** injecting the exception with a healthy Yahoo fallback returned
`Error retrieving rsi data: ...`; Yahoo was never called.

**Remedy:** propagate rate-limit exceptions before the generic handler. Exercise
the complete router with rate-limited Alpha and available Yahoo implementations.

### A08 — P2 — The reported governance identity cannot read client keys

Sources: [client_tools.tf:42](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/infra/litellm/client_tools.tf#L42),
[outputs.tf:35](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/infra/litellm/outputs.tf#L35), and
[governance/main.tf:37](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/infra/litellm/governance/main.tf#L37).
The identity exposed by `agent_governance.service_account` receives `viewer` and
`secretVersionAdder` on client secrets. The governance root reads their contents
through an ephemeral resource. The official
[Google role definitions](https://docs.cloud.google.com/iam/docs/roles-permissions/secretmanager)
require `secretmanager.versions.access`, which neither role includes.

The documented flow fails with 403 for both adoption and key creation unless
additional permissions exist outside the code. With `client_tools_image=""`, the
identity does not exist. Evidence combines declared-grant extraction and official
role definitions; deployed IAM was not queried.

**Remedy:** provide a dedicated governance identity independent of optional jobs,
with narrowly scoped secret access and required version-creation permissions.
Preserve the existing bootstrap identity's restricted permissions.

### A09 — P2 — Database bootstrap validates a different CA from the runtime

Sources: [bootstrap_database.py:52](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/infra/litellm/scripts/bootstrap_database.py#L52)
and [bootstrap_database.py:201](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/infra/litellm/scripts/bootstrap_database.py#L201).
On recovery, the script checks PostgreSQL with the new local CA file, then retains
the existing `litellm-database-ca` version without comparing its contents.

**Mocked evidence:** connections used a replacement CA, bootstrap reported success,
all versions remained `1`, and the retained CA secret was never read. The runtime
can retain incompatible trust after rotation. No live TLS outage was induced.

**Remedy:** compare the persisted CA before SQL mutations and reject differences
with instructions for an explicit rotation workflow.

### A10 — P2 — The npm release gate fails

Sources: [package.json:19](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/frontend/package.json#L19) and the npm lockfile.
`npm audit --omit=dev --audit-level=high` failed for `next 16.3.8` with three
advisories. The full audit flagged six packages: Next and a lint dependency chain.
These counts do not represent six independent exploitable vulnerabilities.

The lockfile already contained `sharp 0.35.5`, the workaround in the
[Image Optimization advisory](https://github.com/advisories/GHSA-2464-fhr4-w9xw).
No `use server` / Server Action or `use cache` appeared in the application, which
are prerequisites for the [other](https://github.com/advisories/GHSA-p3m5-59mp-jv5r)
[two advisories](https://github.com/advisories/GHSA-673q-mjm6-r5xr). No applicable
RCE or DoS was demonstrated. The confirmed issue is the affected framework version
and failure of the existing npm policy.

**Remedy:** review and upgrade Next and its ESLint configuration, inspect the
lockfile, and test. Do not blindly accept the major downgrade suggested by
`npm audit fix --force` for the lint chain.

### A11 — P2 — Worker TLS options are incompatible with asyncpg

Sources: [Scanner database.py:11](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/market-scanner-adk/src/app/services/database.py#L11),
[Momentum job_runner.py:24](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/momentum-adk/app/job_runner.py#L24),
and [session_database.py:63](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/momentum-adk/app/infrastructure/session_database.py#L63).
These adapters translate `sslmode` to `ssl` in SQLAlchemy URLs but retain
`sslrootcert`. The dialect passes it to `asyncpg.connect`, which does not accept it.

**Offline evidence:** a synthetic URL with `sslmode=verify-full` and
`sslrootcert=/etc/database/ca.pem` produced
`connect() got an unexpected keyword argument 'sslrootcert'` before connecting.
The worker fails when this explicit CA configuration is used.

No rule enforces server verification for remote URLs either. `require` encrypts
transport, but its asyncpg context has `check_hostname=False` and
`verify_mode=CERT_NONE`. The reader already builds an explicit `SSLContext` and
validates remote configuration more strictly.

**Remedy:** construct an `SSLContext` from CA options, remove incompatible URL
options, and require certificate and hostname verification for remote connections.
Test incorrect CAs, hostname mismatch, missing TLS mode, and local exceptions.

### A12 — P2 — CI does not run the Scanner writer integration suites

Sources: [scanner.yml:5](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/.github/workflows/scanner.yml#L5),
[scanner.yml:49](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/blob/80e471486a4e1115baf68e6a1cef63e3d236dfed/.github/workflows/scanner.yml#L49), and
[writer integration tests](https://github.com/kaligautier/trading-on-IBKR-with-ADK-/tree/80e471486a4e1115baf68e6a1cef63e3d236dfed/apps/backend/market-scanner-adk/src/test/integration).
The workflow runs only `pytest ... src/test/unit`; it does not run
`test_shared_database.py` or `test_scan_contract.py`. Changes limited to
`database/**` do not trigger this workflow.

There is indirect database verification in the image job:
`scanner_image_smoke.py` applies Liquibase and checks sessions after restart.
The reader also has PostgreSQL integration tests, and Momentum has a database job.
These do not replace the writer suites covering permissions, rollback, report
atomicity, and the full ADK graph contract. All 12 writer integration tests passed
when explicitly run during this audit.

**Remedy:** add a PostgreSQL + Liquibase job executing these suites and trigger it
on SQL changes. Retain the image smoke and its separate guarantees.

## Verification performed at the audited revision

| Scope | Result |
| --- | --- |
| Scanner | 360 unit tests, 12 PostgreSQL/Liquibase/ADK integrations, three domain-session scenarios passed |
| Database scripts | 15 harness and cutover-guard tests passed |
| Momentum | 164 unit tests and 52 PostgreSQL/Liquibase integrations passed |
| Reader | 37 tests passed; one domain scenario was not enabled in this suite; branch-inclusive coverage 95.48%, above the 90% threshold |
| Frontend | 16 tests, ESLint, TypeScript, and production build passed |
| LiteLLM / PR policies | 28 and 20 Python tests passed |
| Terraform | 61 mocked tests passed; eight explicit validations used temporary copies |
| Writer → reader contract | Reader JSON schema matched writer serialization |
| Application ADK / OpenTelemetry | Real tool round trip and seven exported spans passed in each application environment |
| Runtime Python locks | Reader 24, Scanner 98, Momentum 93 packages: no known advisories at audit time |
| LiteLLM images | Installed-package audits failed; see A01 |
| npm | Runtime and full audits failed; see A10 |
| Git history secret scan | Two Gitleaks alerts reviewed: `ui-password` was a Terraform secret identifier, not a password value |
| Local Postman HTTP | Three assertions passed: public liveness, anonymous denial, authenticated empty history with `no-store` |
| Isolated Chrome | `/` and `/docs` loaded; report unavailability was explicit; `/docs` had no horizontal overflow or console errors at 390 px |
| Exact LiteLLM smoke | Repeated migrations, login, routing, persistence after restart, shared RPM through Redis TLS, and global budget after restart passed |
| Exact native LiteLLM smoke | NGINX, real local Terraform import/reconciliation, Gemini/SSE, durable usage, independent USD 3/day budgets, renewal, and global denial after restart passed |

The enumerated suites total **768 passing tests**, including 61 Terraform tests.
Postman assertions, smokes, and compatibility checks are additional and are not
included in that total. The Postman test expecting 401 passed its assertion, but
the CLI returned process exit code 1 because of the HTTP status. The reader's
initial run without a database produced four configuration errors; the complete
suite was subsequently rerun successfully with disposable PostgreSQL.

Both complete LiteLLM smokes used the exact scripts from the audited commit on
`linux/amd64` and exited 0. Only inference-provider responses were simulated.
Functional success does not resolve the image advisories in A01.

Minor UI observation, excluded from the 12 prioritized findings: `/favicon.ico`
returned 404 on the landing page, and Chrome reported missing explicit dimensions
on lazy-loaded images. No blocked user journey was observed.

## Evidence and reproduction

Raw JSON reports, image inventories, probes, reproduction scripts, and logs were
retained locally under `.local/code-audit-20261023/`, which is ignored by Git.
They are **not included in this PR** and are not available in a fresh clone.
The evidence summaries above distinguish mocked, local integration, and installed
artifact checks. Reproductions demonstrated defects at the audited revision;
they are not passing regression tests for subsequent fixes.

To rerun repository checks, use the audited commit in an isolated checkout and
follow its component setup instructions. For example, from that checkout:

```sh
# Requires Docker and uv; inventories the pinned images and queries advisories.
python3 infra/litellm/scripts/audit_images.py --output-dir=/tmp/litellm-code-audit

# Requires Docker; providers are simulated and no paid inference is performed.
DOCKER_DEFAULT_PLATFORM=linux/amd64 python3 infra/litellm/tests/smoke.py
DOCKER_DEFAULT_PLATFORM=linux/amd64 python3 infra/litellm/tests/native_gateway_smoke.py
```

Advisory databases change over time, so a later audit can report different counts
even for the same immutable images. No application suite or security audit was
rerun solely to translate and publish this historical report.

## Limits and remediation order

No penetration test, deployed IAM inspection, cloud mutation, or paid model or
financial-provider call was performed. Real PostgreSQL engines, migrations, and
ADK SDK execution were exercised; provider and LLM responses were simulated.
The checks do not establish real financial-output quality or comprehensive prompt
injection resistance. Rendering a live report through Cloud Run IAM was not
reproduced locally. Linux OS packages in the images were not scanned.

Disposable databases, servers, containers, and the isolated browser were stopped.
Pre-existing containers were preserved; downloaded images remained cached.

Suggested order at the audited revision: images A01; sanitization A02, availability
A03, and TLS A11; calculation/date corrections A04–A07; governance/recovery A08–A09;
npm gate A10 and writer CI coverage A12. Data defects should be addressed before
presenting historical analyses as free of look-ahead bias. Recheck each finding
against current code before implementing follow-up changes.
