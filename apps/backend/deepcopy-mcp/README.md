# Deepcopy MCP

Read-only MCP server on the [Deepcopy API](../deepcopy-api/README.md), built from
the Deepcopy FastMCP template (**FastMCP 4.1.6**). Business services stay
independent of MCP; thin adapters expose tools, a resource, and a prompt.

```text
MCP client -> deepcopy-mcp -> deepcopy-api /ibkr -> IBKR Client Portal gateway
```

No tool places, modifies, or cancels orders.

## Quick start

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and [just](https://just.systems/).
Start the IBKR gateway and the Deepcopy API first (see their READMEs), then:

```bash
just install
cp .env.example .env   # MCP on port 8001, Deepcopy API on 127.0.0.1:8000
just api
```

The HTTP endpoint is `http://127.0.0.1:8001/mcp`; `GET /health` returns
`{"status":"ok"}`. Use `just stdio` for clients that launch their own process.

```bash
uv run --frozen fastmcp call http://127.0.0.1:8001/mcp deepcopy_search_contracts symbol=AAPL
```

## Included capabilities

| Component | Deepcopy API call |
| --- | --- |
| `deepcopy_get_session` | `GET /ibkr/session` |
| `deepcopy_list_accounts` | `GET /ibkr/accounts` |
| `deepcopy_get_account_summary(account_id)` | `GET /ibkr/accounts/{account_id}/summary` |
| `deepcopy_get_positions(account_id, page=0)` | `GET /ibkr/accounts/{account_id}/positions?page=N` |
| `deepcopy_search_contracts(symbol)` | `GET /ibkr/contracts?symbol=...` |
| `guide://deepcopy` | What the tools can and cannot do |
| `review_portfolio` | Reusable prompt, without an LLM call |

The tools exist only when `MCP_DEEPCOPY_API__BASE_URL` and
`MCP_DEEPCOPY_API__TOKEN` are set. Account IDs (`^[A-Z0-9]{1,20}$`), symbols
(uppercase, up to 12 characters) and pages (0 to 1000) are validated before any
call. The token is sent as a bearer token; the Deepcopy API does not check it yet.
A Deepcopy API `503` (IBKR not signed in or session not open) becomes the tool
error `Deepcopy API: not ready`.

Tools declare their title and read-only, non-destructive, idempotent, open-world
hints. The native FastMCP logging middleware records tool arguments, completion,
and duration on stderr. Set `MCP_LOG_TOOL_ARGUMENTS=false` to omit arguments.

## Project layout

```text
src/app/
  application.py         # server factory and middleware
  main.py                # CLI and transports
  core_components/tools/ # portfolio MCP tools
  core_components/       # resource and prompt
  services/              # DTO-to-domain mapping
  models/                # domain models and shared identifiers
  api/deepcopy/          # client/, config/, dtos/request/, dtos/response/
  api/                   # shared HTTP transport, settings, and errors
  config/                # environment settings
  lifespan.py            # API client lifecycle
  auth.py                # JWT verification
  routes/health.py       # liveness probe
  utils/logger.py        # JSON logging to stderr
src/test/                # unit and integration tests (loopback Deepcopy API)
```

## Development

```bash
just check   # ruff, ty and pytest
```

## Connect a client

Replace the path with your clone's location:

```json
{
  "mcpServers": {
    "deepcopy": {
      "command": "uv",
      "args": ["run", "--project", "/absolute/path/apps/backend/deepcopy-mcp", "--frozen", "deepcopy-mcp", "--transport", "stdio"]
    }
  }
}
```

`fastmcp.json` is a server configuration for the FastMCP CLI, not a client config.
For production HTTP, use the application launcher or Docker to apply JWT and
Host/Origin checks. See [deployment](docs/DEPLOYMENT.md).

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Adding a tool](docs/SERVICES_VS_TOOLS.md)
- [Deployment and logging](docs/DEPLOYMENT.md)
- [FastMCP design decisions and sources](docs/FAST_MCP_SERVER_REVIEW.md)
- [Contributing](CONTRIBUTING.md)

