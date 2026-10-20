# Momentum ADK

Independent Python 3.12 package for the private Momentum extraction described in
the [specification](../../../docs/specs/momentum-service.md) and
[execution checklist](../../../tasks/todo.md).

## Current implementation

T01–T05 provide the locked package, ticker/analyst validation, complete financial
output schemas/renderers, typed workflow states and signal normalization.
T06–T08 add the isolated schema and migrated ADK session storage, verified on
disposable PostgreSQL and applied to the existing service database on 2026-10-20.
The live runtime login passed session/event persistence and permission-denial
checks; original Scanner rows and migration history were preserved.
This library has no worker, HTTP entrypoint, image or application deployment yet.
T09 provides the 12 completed-result ORM models with execution correlation;
T10 migrates those tables into the dedicated result database with INSERT/SELECT
permissions only. Transactional persistence is still pending.
The revised target uses `momentum_sessions` and `momentum_results` on the existing
PostgreSQL service, each with a dedicated runtime login. Local tests now verify
the separate session database and cross-database login denial; live cutover is pending.
Financial result storage, the gateway and existing ADK workflow will be ported
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
