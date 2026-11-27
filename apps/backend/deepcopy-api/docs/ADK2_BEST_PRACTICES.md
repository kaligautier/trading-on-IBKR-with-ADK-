# ADK 2.0 best practices

This template uses ADK 2.0 as an orchestration layer. Keep the workflow
definition focused on sequencing and decisions; keep business services and
external integrations behind tools or adapters.

ADK 2.0 is pre-GA. The dependency is intentionally on the 2.x line, but every
upgrade must be verified against the installed runtime and the focused tests.
Do not share session databases or checkpoint storage with an ADK 1.x service.

## Choose the right primitive

| Need | Primitive |
| --- | --- |
| One reasoning step with tools | `LlmAgent` |
| Fixed multi-step flow | `Workflow` with sequential edges |
| Conditional decision | `Event(route=...)` and routed edges |
| Parallel fixed branches | fan-out edges and `JoinNode` |
| Parallel dynamic list | `@node` with `asyncio.gather` |
| Human approval | `RequestInput` at an explicit gate |
| Small persistent facts | `Event(state={...})` |
| Large payloads | Artifacts, not session state |

Use a plain `LlmAgent` when there is no real orchestration problem. A
`Workflow` earns its place when the order, branching, parallelism, retries, or
approval rules matter to the product.

## Typed boundaries

Use Pydantic models between nodes. Set `output_schema` on LLM nodes and
`input_schema` when a downstream node needs a typed value.

```python
from pydantic import BaseModel
from google.adk.agents import LlmAgent


class PortfolioBrief(BaseModel):
    ticker: str
    thesis: str


researcher = LlmAgent(
    name="researcher",
    model="gemini-2.5-flash",
    mode="single_turn",
    output_schema=PortfolioBrief,
    instruction="Return a structured brief for the requested ticker.",
)
```

Inside a function node, name the upstream parameter exactly `node_input`:

```python
def persist_brief(node_input: PortfolioBrief) -> PortfolioBrief:
    return node_input
```

Other parameter names are resolved from `ctx.state`. This is useful for small
facts such as counters, but it is a common source of runtime errors.

## Explicit graph control

Keep orchestration in edges instead of hiding it in prompts:

```python
from google.adk import Event, Workflow


def decide(node_input: PortfolioBrief) -> Event:
    route = "REVIEW" if node_input.ticker else "REJECT"
    return Event(output=node_input, route=route)


root_agent = Workflow(
    name="portfolio_flow",
    edges=[
        ("START", researcher),
        (researcher, decide),
        (decide, review, "REVIEW"),
        (decide, reject, "REJECT"),
    ],
)
```

For parallel branches, join by node name and accept a dictionary in the join
node. Do not rely on an undocumented list ordering.

```python
from google.adk.workflow import JoinNode

join = JoinNode(name="merge_reports")
workflow = Workflow(
    name="parallel_research",
    edges=[
        ("START", (market_report, news_report)),
        ((market_report, news_report), join),
        (join, combine_reports),
    ],
)
```

## Dynamic workflows and bounded retries

Use `@node` when the set of workers depends on the input. Run independent
workers concurrently and cap every loop. An unbounded LLM retry loop is an
operational incident waiting to happen.

```python
import asyncio

from google.adk import Context
from google.adk.workflow import node


@node(rerun_on_resume=True)
async def investigate(ctx: Context, node_input: PortfolioBrief) -> str:
    workers = select_workers(node_input)
    reports = await asyncio.gather(
        *(ctx.run_node(worker, node_input) for worker in workers)
    )
    return "\n".join(reports)
```

Use `mode="single_turn"` for workers that run in parallel. Use `task` when a
coordinator delegates a typed task to a sub-agent. Do not use open-ended chat
mode for deterministic workflow leaves.

## State, sessions, and artifacts

- Pass business data through node output whenever the next node consumes it.
- Use `Event(state={...})` only for small facts needed by later branches.
- Use artifacts for reports, files, and other large values.
- Create `Runner`, `App`, and the session service once at application startup.
- Scope session identifiers by authenticated user and workflow execution.
- Persist resumable state in a production store; in-memory sessions are local
  development only.

## Human-in-the-loop

Place `RequestInput` only at a deliberate approval boundary. Capture the
interrupt and invocation identifiers at the API boundary, return them to the
client, and resume the same invocation with the user's response. Never make a
financial action depend on an unvalidated free-form approval string.

For Momentum, the API must authorize the account before starting the workflow;
the workflow must receive a scoped account reference, not raw credentials.

## Callbacks, tools, and services

- Attach callbacks to `LlmAgent` instances for cross-cutting logging,
  redaction, metrics, and tool-output validation.
- Keep business logic in framework-independent services.
- Make tools thin ADK adapters over those services.
- Use MCP for an external capability boundary; use a custom tool for a small
  local operation.
- Do not make a `@node` a tool. If it needs graph routing, fan-in, or resume,
  keep it as a workflow node or sub-workflow.

## FastAPI and deployment

The ADK runner and session service are application infrastructure, not request
helpers. Construct them once in the application lifespan and reuse them across
requests. Keep the public API and admin API outside the workflow service:

```text
public API/admin API -> authenticated execution request -> ADK2 service
ADK2 service -> private MCP/tools -> external systems
```

For Cloud Run, use authenticated internal calls or a queue for long-running
workflows. Return an execution identifier from the API and let clients poll or
subscribe to status. Do not keep critical workflow state only in process
memory.

## Evaluation and verification

Use unit tests for graph shape, schemas, routing, callbacks, and tool
contracts. Use ADK evaluation for model behavior and tool trajectories. Never
assert exact LLM prose in pytest. Start with a small eval set, then add edge
cases for missing data, denied access, tool failure, retry exhaustion, and
approval rejection.

Before upgrading ADK, verify:

```bash
uv lock --prerelease=allow
uv run pytest -q
uv run ruff check src
python -c "from google.adk import Workflow; print(Workflow)"
```
