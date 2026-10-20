# Momentum ADK

Independent Python 3.12 package for the private Momentum extraction described in
the [specification](../../../docs/specs/momentum-service.md) and
[execution checklist](../../../tasks/todo.md).

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
Local validation passes 87 unit and 48 PostgreSQL integration cases.
This library has no worker, HTTP entrypoint, image or application deployment yet.
The gateway and existing ADK workflow will be ported
in dependency order. The final worker will use the dedicated Cloud Run
Job, isolated PostgreSQL storage and exclusively LiteLLM inference.

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
