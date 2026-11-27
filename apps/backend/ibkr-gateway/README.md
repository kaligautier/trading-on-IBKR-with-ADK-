# IBKR gateway

Docker image of the Interactive Brokers Client Portal gateway used by the
[Deepcopy API](../deepcopy-api/README.md). It contains:

- the official Client Portal gateway, downloaded from IBKR at build time, on
  port **5055** (HTTPS, self-signed certificate);
- a tickler that keeps the session alive (`/v1/api/tickle` every 55 seconds);
- an auto-login server on port **5056** (`/auto-login`, `/auto-login/2fa`,
  `/auto-login/health`), driven by Chromium through Playwright.

```text
deepcopy-mcp -> deepcopy-api -> ibkr-gateway (5055) -> api.ibkr.com
```

## Run locally

```bash
docker compose -f compose.local.yml -p ibkr-gateway-local up -d --build
```

Both ports are bound to `127.0.0.1`. Sign in yourself at
https://localhost:5055; the gateway then answers `GET /v1/api/one/user` with
200. If `POST /v1/api/iserver/auth/status` reports `established: false`, open
the brokerage session through the Deepcopy API (`POST /ibkr/session/init`).

The session belongs to the signed-in IBKR user. Anything that can reach port
5055 can use it, including order endpoints, so never expose the port beyond
the host.

## Files

| File | Role |
| :--- | :--- |
| `api_gateway/Dockerfile` | Java 21 image with Node.js, Playwright Chromium and the gateway |
| `api_gateway/conf.yaml` | Gateway configuration (port, allowed IPs, IBKR endpoint) |
| `api_gateway/run_gateway.sh` | Starts the gateway, the tickler and the auto-login server |
| `api_gateway/healthcheck.sh`, `tickler.sh` | Container health check and session keep-alive |
| `api_gateway/auto_login/` | Auto-login server (`server.js`, `login.js`) |
| `compose.local.yml` | Local container with localhost-only ports |

## Origin

Imported from `kaligautier/deep-copy-finary` (`apps/ibkr-mcp-gateway`, commit
`2203792`), itself a fork of IB_MCP by Ruben Contesti under the MIT licence
(see [LICENSE](LICENSE)). The original MCP server is not kept: the read-only
[Deepcopy MCP](../deepcopy-mcp/README.md) goes through the Deepcopy API instead.
