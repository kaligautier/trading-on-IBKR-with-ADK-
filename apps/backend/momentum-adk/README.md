# Momentum ADK

Independent Python 3.12 package for the private Momentum extraction described in
the [specification](../../../docs/specs/momentum-service.md) and
[execution checklist](../../../tasks/archive/momentum-worker-todo.md).

## Current implementation

T01–T05 provide the locked package, ticker/analyst validation, complete financial
output schemas/renderers, typed workflow states and signal normalization.
T06–T08 provide migrated ADK session storage. T09–T10 provide 12 completed-result
models and their migrations. T11 writes all financial sections and execution
correlation in one transaction; failures roll back the whole result.
The target is one database, `momentum`, with `_sessions` (5 ADK tables) and
`_analysis` (12 result tables). Separate runtime logins restrict each connection
to its own schema; result access is INSERT/SELECT only. Both pools are bounded.
The unified layout was applied and verified remotely on 2026-10-20; obsolete
Momentum databases and the shared legacy schema were removed after private backups.
Local validation passes 136 unit and 49 PostgreSQL integration cases.
The worker now includes the original market-data adapters, twelve agent roles,
analyst/debate graph, execution memory and durable ADK runtime. All model roles use
the native LiteLLM gateway exclusively. A shared gate permits two concurrent model
calls and spaces request starts by 6.5 seconds to respect the virtual key policy.
The bounded worker runs as `python -m app.job_runner`; its non-root image is deployed
by the independent [Terraform root](../../../infra/momentum/README.md).
The private HTTP dispatcher remains a separate, unimplemented component.

Required runtime variables are `LITELLM_API_BASE`, `LITELLM_API_KEY`,
`MOMENTUM_SESSION_DATABASE_URL`, `MOMENTUM_RESULT_DATABASE_URL` and
`TA_ANALYSIS_REQUEST` (AnalysisRequest JSON). Both database URLs must explicitly
name `momentum`. Model aliases are configurable through `MOMENTUM_QUICK_MODEL`
and `MOMENTUM_DEEP_MODEL`. Credentials belong in Secret Manager or ignored local
files, never in command examples or Terraform variable values.

Use `scripts/verify_result.py SESSION_ID` with the result runtime credential to
independently verify a committed analysis and its token/tool counters. The worker
logs a completion event only after the result transaction commits.

## Local checks

From this directory, with uv 0.9.17 and Python 3.12:

```sh
uv lock --check --python 3.12
uv sync --frozen --python 3.12
uv run --frozen ruff check app tests
uv run --frozen ruff format --check app tests
TZ=UTC uv run --frozen pytest -q tests/unit
uv build --wheel
```

`just check` runs these checks together. Imports and unit tests need no credentials,
network services or source repository. Each application has its own environment;
do not add sibling applications to `PYTHONPATH`.

Install dependencies through the committed `uv.lock`. The application and wheel
require OpenTelemetry API/SDK 1.45.1 to fix CVE-2026-114603. ADK 2.6.1 still caps
these dependencies at 1.42.1, so the project contains a narrow, tested uv override.
A standalone resolver without that override fails rather than silently installing
the vulnerable version. For an internal wheel, first prepare the frozen environment
with `uv sync --frozen --no-dev`, then install the wheel there with
`uv pip install --python .venv/bin/python --no-deps path/to/momentum_adk.whl`.
CI verifies both the wheel requirements and installed versions outside the checkout,
and exercises actual ADK model/tool spans with the fixed SDK. Remove the override
when ADK supports the corrected dependency pair directly.

## Source and adaptation

Domain contracts/value objects and their original regression cases come from
DeepCopy commit `38d0736a4bf778ebcb81dbf4acef52fd2dd34e77`, under Apache-2.0
(see the repository [license](../../../LICENCE)). Original copyright notices are
retained. Packaging and CI are independent. Invalid ticker/analyst input now raises
validation errors instead of raw attribute/type errors. Successful requests,
role order, defaults, result fields and resume correlation retain the source
contract. All 16 financial JSON schemas and 12 renderer ASTs match the source;
workflow state and rating parser are unchanged. A requester label is audit
context, not authorization.

### Durable private memory

The worker reads user-scoped decisions and reflections from
`momentum._analysis.trading_memory`, using its existing result connection pool.
Apply the additive domain Liquibase migration before rolling out this worker.
Readers and the session writer cannot access this private table. Results, the
current decision and resolved reflections commit in one transaction; an identical
execution replay is a no-op, while conflicting completion content is rejected.

Context retrieval is deterministic and bounded (five resolved ticker entries,
three other resolved entries, at most sixteen pending ticker outcomes). Market
lookups happen after the read session closes. Reflections reference stable memory
IDs, so two analyses of the same ticker/date remain distinct. A new process needs
only PostgreSQL access to recover memory; no local file fallback or automatic
import of historical `/tmp` files remains. Cache and diagnostic paths may still
use temporary storage.
