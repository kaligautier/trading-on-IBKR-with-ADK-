# Spec: Rebuild domain databases with persisted sessions and analyses

Status: implementation approved by the user for local application and tests.
Remote execution is not part of this local validation. Replaces the previous data-preserving
migration specification, its compatibility requirements and recovery procedure.

## Objective and authorized scope

Rebuild application storage on the existing Aiven PostgreSQL service. The user
explicitly accepts losing existing Scanner and Momentum application data and
migration history, requires no backward compatibility, and will regenerate
Scanner analyses with a new run. Sessions and analyses must both persist.

```text
Existing Aiven PostgreSQL service
├── market_scanner
│   ├── _sessions   ADK sessions, events, states and SDK metadata
│   ├── _analysis   reports, assets and horizons
│   └── liquibase  fresh domain migration history
├── momentum
│   ├── _sessions   ADK sessions, events, states and SDK metadata
│   ├── _analysis   domain analysis tables where implemented
│   └── liquibase  fresh domain migration history
├── litellm         retain native data/schema and credentials
└── defaultdb       no Scanner/Momentum application data after cleanup
```

Momentum schema names include literal leading underscores as requested. Apply
this convention to Scanner as well. Agent and reader API of a domain share its
base with distinct privileges. Scanner session persistence is required, even when
there are no old sessions to import. Momentum's `_analysis` exists even if its
future result tables are not implemented; building that feature is out of scope.

The authorized reset covers Scanner/Momentum data in their dedicated databases
and their positively identified legacy objects in `defaultdb`. Preserve LiteLLM,
managed-service/system objects, unrelated applications and the Aiven service.
Do not treat permission to rebuild application storage as permission to drop every
service database. Existing credentials may be reused if valid and least-privileged.

No data copying, historical checksum preservation, legacy-schema fallback,
compatibility views, reverse synchronization or 24-hour observation window is
required. Do not build those mechanisms. Failure recovery is repair and rerun
against the new empty schema; no old-data recovery guarantee is offered.

## Current evidence

- [Scanner job](../../apps/backend/market-scanner-adk/src/app/jobs/daily_scan.py)
  explicitly uses `InMemorySessionService`. It must use PostgreSQL instead.
- [ADK application](../../apps/backend/market-scanner-adk/src/app/application.py)
  does not supply persistent session configuration to `get_fast_api_app`. Inspect
  the pinned SDK integration point and configure it consistently with the job.
- Scanner's lockfile resolves Google ADK 2.6.1. Match its exact session tables,
  keys, indexes and schema version; this is not permission to upgrade the SDK.
- Scanner writer and reader already accept `DATABASE_SCHEMA`; select `_analysis`
  and remove legacy defaults. Preserve the report-v3 public payload contract.
- The separately inspected Momentum foundation at `19641ad` uses a single pooled
  session connection and hardcodes the `momentum` schema. Coordinate with its
  authoritative successor and change both inspection and search path to `_sessions`.
- Code evidence is not live deployment evidence. Identify actual consumers,
  runtime revisions, database objects and ownership before reset.

## Required behavior

### Fresh database ownership and migrations

1. Keep one independent changelog entry point and `liquibase` history per domain.
   Fresh chains create the final schemas directly, without intermediate legacy
   schemas. Applied history is intentionally discarded with old application data;
   old creation files may be replaced because no old database will be upgraded.
2. Create `_sessions` tables through Liquibase using the pinned SDK definition.
   ADK runtimes may validate existing tables, never create or migrate them.
3. Scanner `_analysis` retains the existing report/asset/horizon model. Do not
   replace durable typed analyses with session JSON or infer reports from events.
4. Runtime writers have required session DML and business writes, no schema DDL
   or migration-metadata rights. SDK metadata is read-only. Reader roles can SELECT
   analyses but cannot access `_sessions`, including via inherited/PUBLIC grants.
5. Restrict effective database CONNECT grants by domain. Set explicit per-database
   role/schema settings; runtime/admin credentials are never interchangeable.
6. Reset commands validate expected service identity and an exact object/database
   allowlist, stop affected writers, and refuse unexpected dependencies. They must
   never drop `litellm` or the whole `defaultdb`, nor use uncontrolled CASCADE.
   A repeated reset explicitly erases newly generated application data too; retries
   must not invoke it automatically after a failed deployment or scan.

### Persistent Scanner execution

- Job and interactive ADK service use the same PostgreSQL session backend in
  `market_scanner._sessions` with explicit app/user/session identifiers.
- Session state/events survive process restarts and are readable through the
  authenticated ADK session interface. No production in-memory fallback on error.
- A successful scan leaves both its durable session and a durable `_analysis`
  report. Preserve an unambiguous correlation, including the current scheduled
  marker convention; do not silently rewrite the public report contract.
- Session storage failure fails the run visibly. Session/event and analysis
  persistence need not be one SQL transaction, but a run cannot report success
  until both have succeeded. Diagnose partial outcomes without erasing evidence.
- Define retry behavior for an existing scheduled session ID: detect a completed
  run, or resume/reject explicitly based on supported SDK behavior. Do not blindly
  recreate a session or replay report writes. Test retries without claiming an
  unimplemented exactly-once guarantee.
- Deleting/expiring a session must leave its analysis readable. No cross-schema
  deletion cascade or mandatory session FK. No automatic retention policy added.
- Use one bounded session pool per process (`pool_size=1`, `max_overflow=0`) and
  retain bounded analysis pools. Account for both pools, replicas and concurrent
  jobs in role/service limits. Adding persistent Scanner sessions can increase
  total connections; measure the combined budget rather than claiming otherwise.
- Close session and analysis engines on normal shutdown and errors.

### Deployment and fresh verification

- Identify and quiesce all affected jobs/services before reset. Deploy only code
  selecting `_analysis`/`_sessions`, pinned image digests and numeric secret versions
  pointing at the correct domain database. Preserve TLS verification and CA options.
- Validate fresh migrations and role rights before allowing runtime traffic.
  Legacy revisions must not keep running against removed application schemas.
- After reset/deployment, perform one new Market Scanner run and prove the stored
  analysis, session/events and reader response survive process restart. This run
  may call configured external model/data providers; execute only when the user's
  request to rerun applies and runtime prerequisites are ready.
- Verify Momentum with a synthetic persisted session round trip. A full new
  Momentum analysis engine or public API is outside this storage task.
- Stop on unknown ownership or wrong target identity. This is a concrete scope
  check, not a renewed permission request for the already authorized data loss.

## Tech stack and project structure

Use existing Python 3.12+, asyncpg/SQLAlchemy, pytest/Ruff, pinned ADK and Liquibase
5.0.4. Test PostgreSQL against the actual server major version as well as existing
local PostgreSQL 17 fixtures when different. No new service tier or SDK upgrade.

| Location | Responsibility |
| --- | --- |
| `database/changelog/` | Fresh domain session/analysis chains. |
| `database/scripts/`, `database/tests/` | Purpose-built reset/bootstrap commands and disposable acceptance checks. |
| `apps/backend/market-scanner-adk/src/app/` | Persistent session adapter, scheduled job and ADK service integration. |
| `apps/backend/market-scanner-api/` | Analysis-only reader configuration and access tests. |
| Authoritative `apps/backend/momentum-adk/` | Session adapter and existing analysis storage configuration. |
| `infra/`, `infra/reader/`, actual Momentum deployment owner | Explicit schemas, secret versions, pools and runtime release. |
| `tasks/plan.md`, `tasks/todo.md` | Updated execution plan/checklist; old migration tooling is superseded. |

## Commands

Existing baseline checks; run component commands from that component directory:

```sh
# Repository root
git diff --check
docker build -t local/deep-copy-liquibase:5.0.4 database
terraform fmt -check -recursive infra
# apps/backend/market-scanner-adk
uv sync --frozen
TZ=UTC uv run --frozen pytest -q src/test/unit
uv run --frozen ruff check src
# apps/backend/market-scanner-api
uv run --frozen pytest -q src/test/unit
uv run --frozen ruff check src scripts
uv run --frozen mypy
```

The new reset/rehearsal commands are deliverables in the checklist, not existing
utilities. Their live invocation must include verified targets and protected
credential references. No secret URLs in shell arguments, output or Git.

## Code style

Use existing typed Python, 88-column Ruff style, explicit engine lifecycle and
parameterized SQL values. Quote validated identifiers separately. Follow this
existing bounded-engine pattern, with the session namespace selected explicitly:

```python
create_async_engine(
    database_url,
    pool_size=1,
    max_overflow=0,
    hide_parameters=True,
    connect_args={"server_settings": {"search_path": "_sessions, pg_catalog"}},
)
```

## Testing strategy and success criteria

Use real disposable PostgreSQL, Liquibase and the pinned ADK adapter. Mock external
providers for local tests; a final fresh live Scanner run establishes deployed
behavior. Do not run destructive fixtures against remote databases.

| ID | Required evidence |
| --- | --- |
| DB-01 | Live inventory identifies exact reset targets and all consumers; LiteLLM/system/unrelated objects excluded. |
| DB-02 | Fresh databases, final schemas and independent histories created; second Liquibase update is a no-op. |
| DB-03 | Runtime roles can perform only intended DML; readers cannot access sessions; cross-domain access and runtime DDL fail. |
| DB-04 | Scanner job and ADK service persist/read session state and events after restart, with no memory fallback. |
| DB-05 | New Scanner analysis is stored in `_analysis`, linked to its session and readable through the API after restart; report-v3 stays valid. |
| DB-06 | Momentum `_sessions` passes real SDK round trip; `_analysis` has only implemented domain tables. |
| DB-07 | Session deletion preserves analysis; session storage errors, partial runs and repeated IDs have explicit tested behavior. |
| DB-08 | Combined session/analysis pools fit reviewed role/service limits; engines close on failure/shutdown. |
| DB-09 | Wrong identity, unexpected dependencies, unsafe secret files and unrequested automatic resets fail safely. |
| DB-10 | Deployed image/schema/secret references match final layout; no old consumer uses legacy storage. |
| DB-11 | `defaultdb` contains no Scanner/Momentum data after authorized cleanup; LiteLLM and unrelated objects remain intact. |
| DB-12 | One fresh live Scanner run proves durable sessions and analysis; documentation separates local/CI/live evidence. |

## Boundaries and review state

- **Always:** preserve unrelated dirty worktrees; keep infrastructure as code;
  limit PRs to one application component and 1,000 counted lines; verify actual
  targets and data ownership; run focused tests; never publish secret/data artifacts.
- **Review gates:** task checklist review before implementation under the invoked
  spec-driven skill. The user's instructions already authorize dropping/rebuilding
  Scanner/Momentum storage without old-data recovery; do not request that same
  permission again. Changed scope or unknown ownership still requires resolution.
- **Never:** destroy LiteLLM/system/unrelated data, silently reset after a failure,
  retain legacy compatibility machinery, or claim the new run succeeded without
  durable analysis/session evidence.

Remaining operational inputs: actual deployment owner/identities and measured
connection capacity. Existing in-memory session history cannot be recovered;
new executions populate the fresh store. The [plan](../../tasks/plan.md) and
[checklist](../../tasks/todo.md) must implement this rebuild scope, not the superseded
copy-and-cutover plan.

Reference: [ADK session services](https://adk.dev/sessions/session/) explains
persistent session storage; implementation must inspect the locally pinned SDK.
