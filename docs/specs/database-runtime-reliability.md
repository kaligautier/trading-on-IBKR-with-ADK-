# Spec: verified worker TLS, durable Momentum memory and connection capacity

Status: **SPECIFY — awaiting human validation**. No implementation is claimed.
Baseline: `bf6e2e2`. Requested on 23 October 2026.

## Objective

Make Scanner and Momentum database connections verifiable, preserve Momentum's
trading memory across worker instances, and prevent the shared PostgreSQL service
from exhausting its connection capacity under the supported workload.

The users are the operator running analyses and the user whose past decisions
and reflections should enrich future analyses without leaking to another user.

Scope assumptions surfaced before drafting:

- The three requested problems are worker TLS, persistent Momentum memory and
  the global connection budget, as enumerated in the latest conversation.
- Keep the existing domain databases and the observed 15-connection service tier.
  Increasing paid capacity is not the default solution.
- Deliver application code, additive migrations, infrastructure configuration,
  regression tests and operational instructions. Live rollout is a separate gate.
- Historical files cannot be recovered from destroyed containers. Do not invent
  past reflections or automatically ingest arbitrary legacy markdown files.
- General Scanner/result replay idempotency, backup automation and broader audit
  recommendations are outside these three fixes. Memory writes must nevertheless
  be idempotent because durability without safe retry would be incorrect.

## Current evidence

- Scanner `async_database_url()` and Momentum `database_address()` translate
  `sslmode` to `ssl` but retain `sslrootcert` as an unsupported asyncpg keyword.
  Both result-engine paths reproduced a TypeError before connection; session
  adapters use the same URL conversion pattern.
- Momentum `job_runner.execute()` creates a `TradingMemoryLog` at the configured
  local path and calls `memory.complete()` after the result transaction commits.
  Its Dockerfile defaults to `/tmp/momentum/memory.md`.
- The Momentum reader reached PostgreSQL 18.6 using verified TLS during the audit;
  `max_connections` was 15. Reserved/provider slots and the complete deployed
  workload inventory still require refresh. This is not a measured saturation.
- Individual pools/role ceilings exist. Job parallelism does not limit concurrent
  executions, and revision overlap can multiply service pools.

## Required behavior

### A. Verified TLS for workers

Both session and result connections in both workers must:

1. Require certificate-chain and hostname verification for remote PostgreSQL.
2. Support a configured readable CA file, with system trust where explicitly
   supported. Convert URL options into the driver's supported SSL interface.
3. Reject unknown/conflicting TLS options and remote insecure modes early,
   without emitting passwords, URLs, CA contents or business payloads.
4. Permit explicitly disabled TLS only for loopback development fixtures.
5. Preserve bounded pools, timeouts, parameter hiding, domain validation and
   schema search paths; close pools after success, failure and cancellation.
6. Wire CA secret mounts/references through worker Terraform and local examples.
   Merely changing Python while deployed URLs still request weaker TLS is not
   sufficient for a live completion claim.

### B. Durable, isolated Momentum memory

The production worker must use PostgreSQL as the authoritative memory store,
using its existing domain database. Proposed placement is private tables under
`_analysis`, excluded from consultation-reader grants. The memory records include:

- User, session and invocation identifiers, a stable memory-record identity,
  ticker, analysis date, decision text and creation timestamp.
- Pending/resolved outcome state, raw and benchmark-relative returns, holding
  period, reflection text and resolution timestamp when available.

Required semantics:

1. Context retrieval and pending-outcome selection always include user identity.
   Preserve the current same-ticker/cross-ticker context behavior with bounded,
   deterministic reads. Define a bounded batch of pending outcomes per execution.
2. Associate a reflection with its original memory-record identity. Ticker/date
   alone cannot identify two legitimate decisions on the same day.
3. Commit the completed analysis and its new decision memory atomically through
   the existing result transaction. Include reflection updates in that transaction
   where they are produced by this execution. A failed commit leaves neither a
   partial decision nor partially updated reflections.
4. Enforce uniqueness for memory execution identity, including user scope. Retry
   and concurrent completion must not duplicate memory; define handling of an
   already-completed execution and of conflicting content explicitly.
5. A second independent process must retrieve the committed memory with a new,
   empty local filesystem. Production must not silently fall back to markdown
   when the database fails. `/tmp` may remain for replaceable caches.
6. Perform model and market-data calls outside open database transactions; use the
   bounded existing results pool rather than adding an unbudgeted memory pool.
7. Add Liquibase migrations and narrowly scoped privileges. Preserve existing
   baselines, history, result data and session schemas. Test both fresh installs
   and upgrades; an existing database must adopt its baseline before new changes.
8. Existing in-memory/test adapters may support deterministic tests. Document the
   behavior of local/library entry points; do not leave a second production path
   that silently continues writing authoritative memory to `/tmp`.

### C. Enforced connection budget

Inventory Scanner HTTP/job result and session pools, both readers, Momentum jobs,
LiteLLM admin/gateway/migrations, administrative access, provider consumers and
overlapping deployments on the actual shared server.

Record a machine-checkable budget, source configuration and assumptions. Count
maximum open connections, including idle pools, not HTTP request concurrency.
The safety condition is:

```text
application peak + migration allowance + operator allowance
    <= max_connections - provider/reserved capacity
```

Reserved capacity must come from authoritative settings/provider evidence rather
than guessing that all 15 slots are available. Do not double-count allowances.
The budget must reserve at least one usable operator slot and explicitly model
the migration/deployment operating mode.

1. Align pool sizes, runtime-role limits, supported worker overlap and deployment
   behavior with that budget. The new memory persistence must fit inside it.
2. Bound admission of concurrent job executions across processes, or enforce an
   equivalent safe admission mechanism. `parallelism=1`, a process-local lock,
   or a statement saying “avoid overlaps” is insufficient.
3. Over-capacity work must receive a bounded, observable rejection/defer outcome
   before expensive model work, without partial writes or a retry storm. Account
   for connections needed by the admission mechanism itself.
4. Include old/new revision overlap and Cloud Run temporary excess instances.
   Hard database limits are the final protection, but do not count routine
   `too many connections` failures as successful admission control.
5. A configuration change that exceeds the budget must fail validation. Describe
   a safe deployment/migration sequence and cleanup on cancellation/crash.
6. Prefer existing PostgreSQL/application capabilities. A new queue, pooler,
   paid service or larger DB tier requires explicit scope approval.

## Tech stack

Python 3.12 worker packages; Google ADK 2.6.1; SQLAlchemy 2.x async engine; asyncpg;
PostgreSQL 18; Liquibase 5.0.4; Terraform/Cloud Run/Secret Manager. Use the checked-in
application locks and Terraform provider locks. Ruff is pinned at 0.17.2.
No new runtime dependency is assumed.

## Project structure

- `apps/backend/market-scanner-adk/src/app/services/`: Scanner engines and sessions.
- `apps/backend/momentum-adk/app/`: runner, memory services, result repository and
  infrastructure adapters; `tests/unit/` and `tests/integration/` contain tests.
- `database/domains/momentum/`: immutable baseline and additive memory migration.
- `database/testing/`, `database/tests/`: disposable PostgreSQL and migration tests.
- `infra/market-scanner/`, `infra/momentum/`: worker TLS and execution limits.
- `infra/reader/`, `infra/momentum-api/`, `infra/litellm/`: budget participants;
  change only configuration necessary to meet the shared budget.
- `docs/specs/database-runtime-reliability.md`: this specification.
- `tasks/plan.md`, `tasks/todo.md`: later validated plan and task list. Existing
  unrelated task documents must be preserved/archived explicitly, not overwritten.

## Commands

Run from the repository root unless stated otherwise. These are existing baseline
commands; the validated plan will add exact new TLS and capacity test commands.

```sh
uv sync --project apps/backend/market-scanner-adk --frozen --python 3.12
uv sync --project apps/backend/momentum-adk --frozen --python 3.12
uv sync --project apps/backend/market-scanner-api --frozen --python 3.12
uv sync --project apps/backend/momentum-api --frozen --python 3.12
just lint
uv run --project apps/backend/momentum-adk --frozen pytest -q apps/backend/momentum-adk/tests/unit
python3 database/testing/rehearse.py
uv build --project apps/backend/momentum-adk --wheel
docker build -t local/deepcopy-database:5.0.4 database
terraform -chdir=infra/momentum fmt -check -recursive
terraform -chdir=infra/momentum init -backend=false -input=false -lockfile=readonly
terraform -chdir=infra/momentum validate
terraform -chdir=infra/momentum test
git diff --check
```

Run the same Terraform checks for each changed root. The database rehearsal uses
owned local containers only. Live `plan`, migration and verification commands
must name reviewed targets and private credential files; never inline credentials.

## Code style

Use typed boundary objects, snake_case, small cohesive functions, existing error
redaction and Ruff conventions. Keep synchronous external calls off async DB
transactions. The existing repository expresses transaction ownership clearly:

```python
async def save(self, execution: WorkflowExecution) -> None:
    async with self._session_factory() as session, session.begin():
        await self._result_writer.write(session, execution)
```

Extend that transaction boundary for memory rather than adding a second commit
after it. Success logs should report event/status and safe correlation fields,
never connection URLs, decisions, prompts or credential values.

## Testing strategy and success criteria

Use pytest/pytest-asyncio, disposable PostgreSQL, local certificates and existing
Terraform mock tests. Do not invoke paid model/provider services in CI.

- **TLS-1:** both workers' session/result connections succeed against a local
  PostgreSQL TLS fixture with a trusted CA and matching hostname.
- **TLS-2:** untrusted CA, wrong hostname, missing CA file, remote insecure modes
  and conflicting options fail safely; loopback no-TLS fixtures still work.
- **MEM-1:** a new process with empty `/tmp` reads prior decisions/reflections;
  another user cannot retrieve or mutate them, including pending outcomes.
- **MEM-2:** fault injection between result and memory writes rolls everything
  back; sequential/concurrent retry produces one memory record per execution.
- **MEM-3:** distinct same-ticker/same-date executions stay distinct; reflections
  update only their intended record. Reads are bounded and deterministic.
- **MEM-4:** migrations apply on fresh and adopted fixtures, repeat safely, retain
  existing records and deny consultation readers access to private memory.
- **CAP-1:** an executable budget validates every configured consumer and both
  steady-state and release/migration operating modes against the available slots.
- **CAP-2:** concurrent job/reader/LiteLLM-pool simulations and overlapping
  revisions respect the budget; excess work fails/defer predictably before model
  calls, and the operator allowance remains usable.
- **CAP-3:** failed/cancelled workers release admission and connections; repeated
  executions do not leak slots. Deliberately excessive config fails validation.
- **REG-1:** existing persistence, session, reader, packaging and infrastructure
  tests pass; no secret appears in captured failure diagnostics or PR artifacts.
- **OPS-1:** record separate evidence for local validation and eventual live
  rollout. Until deployed config, remote TLS and real shared capacity are verified,
  report “implementation verified locally”, not “production fixed”.

## Boundaries

- **Always:** follow SPECIFY → PLAN → TASKS → IMPLEMENT validation gates; use
  additive migrations; preserve dirty worktrees; keep exact failure evidence;
  run relevant checks before commits; respect PR size/component policies.
- **Ask first:** validate this specification before planning; validate the plan
  and tasks before subsequent phases. Obtain approval for live migration/apply,
  new services/dependencies, changed paid capacity or destructive historical-data
  remediation. Schema additions described here are part of the proposed scope.
- **Never:** edit applied baseline checksums, disable TLS verification remotely,
  commit secrets, delete production history, bypass protection, treat role
  ceilings as reserved capacity, or silently fall back to temporary memory.

## Open decisions for validation

1. Confirm the three-problem scope and PostgreSQL memory proposal above.
2. Approve keeping the present DB tier and using bounded admission when demand
   exceeds safe capacity. Exact allocations depend on the live reserved-slot and
   provider-consumer inventory and must be resolved in the technical plan.
3. The requested PR is the specification entry point. Current required policy
   permits at most one application component per PR; implementation must use
   linked, dependent PRs if it changes both workers. Do not weaken that policy.

## References

- [Domain database guide](../../database/README.md)
- [Original DB audit](../database-audit-2026-10-23.md)
- [asyncpg connection interface](https://magicstack.github.io/asyncpg/current/api/index.html)
- [PostgreSQL connection slots](https://www.postgresql.org/docs/18/runtime-config-connection.html)
- [Cloud Run maximum instances](https://docs.cloud.google.com/run/docs/configuring/max-instances)
