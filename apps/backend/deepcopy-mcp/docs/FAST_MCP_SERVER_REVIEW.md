# FastMCP decisions and sources

The November 4–5, 2026 review covered 51 accessible pages and one old gateway link
returning 404. URLs and source hashes are preserved in
[`fastmcp-sources.json`](fastmcp-sources.json).

The template pins **FastMCP 4.1.6**. Public documentation can describe newer APIs:
the reviewed Skills page targeted 4.2.0. Check the installed runtime before
adopting an example.

| Area | Template decision | Documentation |
| --- | --- | --- |
| Registration | Explicit server factory and component registration | [Server](https://gofastmcp.com/servers/server), [Local provider](https://gofastmcp.com/servers/providers/local) |
| Tools | Strict inputs, typed outputs, explicit annotations | [Tools](https://gofastmcp.com/servers/tools) |
| Resources and prompts | Calculator guide and reusable instruction, no model call | [Resources](https://gofastmcp.com/servers/resources), [Prompts](https://gofastmcp.com/servers/prompts) |
| Logging | Native `LoggingMiddleware`, bounded argument payloads, stderr | [Middleware](https://gofastmcp.com/servers/middleware) |
| Dependencies | Services injected from lifespan; one client per API | [Dependencies](https://gofastmcp.com/servers/dependency-injection), [Lifespan](https://gofastmcp.com/servers/lifespan) |
| Authentication | Verify externally issued JWTs; require expiration and scopes | [Token verification](https://gofastmcp.com/servers/auth/token-verification), [Authorization](https://gofastmcp.com/servers/authorization) |
| Transport | Local STDIO and stateless HTTP with Host/Origin checks | [HTTP deployment](https://gofastmcp.com/deployment/http) |
| Compatibility | Optional resources/prompts-as-tools transforms and listing pagination | [Transforms](https://gofastmcp.com/servers/transforms/transforms), [Pagination](https://gofastmcp.com/servers/pagination) |
| Observability | Native MCP spans with an optional OpenTelemetry SDK | [Telemetry](https://gofastmcp.com/servers/telemetry) |

Interactive OAuth, persistent sessions, Redis-backed tasks, sampling, and Code Mode
remain extensions. Add them only with tests for their identity, storage, and protocol
requirements. Visibility rules and read-only annotations do not replace authorization.

