# Adding a tool

A **service** accepts Python values and returns a model. A **tool** adapts that
service to MCP: it describes inputs, declares behavior, and translates known errors.

For example, `core_components/tools/portfolio_tools.py` calls `PortfolioService`.
The service builds a `GetProductRequest`, calls `CatalogClient`, and maps the
`ProductResponse` DTO to the `Product` domain model.

1. Define the input/output models in `models/`.
2. For an external API, add its client, config, and request/response DTOs under
   `api/<name>/`. Keep routes and wire formats there.
3. Implement business logic and DTO mapping in `services/`.
4. Register the adapter in `core_components/tools/` and wire its client in `lifespan.py`.
5. Test the client, service, and MCP contract through `Client(create_server(settings))`.

Use `Annotated[..., Field(description="...")]` for parameter descriptions and
`ToolAnnotations` for behavior hints:

| Annotation | Meaning |
| --- | --- |
| `title` | Human-readable display name |
| `readOnlyHint` | Does not modify its environment |
| `destructiveHint` | May perform destructive updates |
| `idempotentHint` | Repeated calls have no additional effect on the environment |
| `openWorldHint` | Interacts with external systems |

Local-only tools use `openWorldHint=False`; API tools use `True`.
All four are read-only and non-destructive. Idempotency describes side effects,
not whether a clock or stock query returns the same value on every call.
These hints do not grant or enforce permissions.

Keep `Context` and `Depends` in adapters. Raise `ToolError` for known business
errors; let FastMCP mask unexpected errors. Use async clients with explicit
timeouts and lifespan cleanup for network calls.

Logging is centralized in `application.py` through FastMCP's `LoggingMiddleware`.
See [logging settings](DEPLOYMENT.md#logging).
