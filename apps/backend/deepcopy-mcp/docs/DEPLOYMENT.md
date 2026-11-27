# Deployment

## Docker

```bash
just build
just run
```

The image pins Python and uv by digest, installs locked runtime dependencies,
and runs as UID/GID `10001:10001`. It supports a read-only filesystem.
`start_server.sh` forwards signals; Uvicorn has 30 seconds for graceful shutdown.

## Production

Create `.env.production` with your identity provider's values:

```dotenv
MCP_ENVIRONMENT=production
MCP_TRANSPORT=http
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_AUTH_MODE=jwt
MCP_JWT_JWKS_URI=https://identity.example.com/.well-known/jwks.json
MCP_JWT_ISSUER=https://identity.example.com/
MCP_JWT_AUDIENCE=deepcopy-mcp
MCP_REQUIRED_SCOPES=["mcp:access"]
MCP_ALLOWED_HOSTS=["mcp.example.com","127.0.0.1"]
MCP_ALLOWED_ORIGINS=[]
MCP_LOG_TOOL_ARGUMENTS=false
```

```bash
just run-prod .env.production
```

Replace example domains. Production requires HTTP and RS256 JWTs with the configured
issuer, audience, scopes, and expiration. JWKS must use HTTPS. The issuer must
match exactly, including any trailing slash. The server verifies tokens; clients
obtain them from the IdP. Interactive OAuth login is not included.

Terminate TLS at your reverse proxy, preserve `Host`, and disable response buffering
for MCP streaming. Configure connection limits, request limits, and CPU/memory on
the hosting platform. Cross-origin browser clients need explicit CORS middleware.

`GET /health` is public and checks liveness only. Verify authenticated MCP calls
and rejection cases before release. Keep the previous image digest for rollback.
No cloud resources or deployments are created automatically.

## Logging

Application logs go to stderr as JSON, leaving stdout available for STDIO MCP.
The native [FastMCP LoggingMiddleware](https://gofastmcp.com/servers/middleware)
logs `tools/call` requests, completion or failure, and elapsed time.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MCP_LOG_LEVEL` | `INFO` | Log level |
| `MCP_LOG_TOOL_ARGUMENTS` | `true` | Include tool names and arguments in request payloads |
| `MCP_LOG_MAX_PAYLOAD_LENGTH` | `1000` | Maximum logged payload characters, followed by `...` if truncated |

Set `MCP_LOG_TOOL_ARGUMENTS=false` when inputs contain sensitive data.
The middleware logs MCP payloads, not HTTP authorization headers or configured
upstream tokens. It also records error messages. Truncation is not redaction.

## Tracing

`just build-traced` builds an image with the optional OpenTelemetry dependencies.
Enable it with `MCP_TELEMETRY_ENABLED=true` and the appropriate `OTEL_*` variables,
including the collector endpoint. FastMCP supplies native MCP spans; do not add a
second MCP instrumentor. The minimal image rejects tracing without the extra.

External collector delivery and the target IdP must be verified in the deployment
environment.
