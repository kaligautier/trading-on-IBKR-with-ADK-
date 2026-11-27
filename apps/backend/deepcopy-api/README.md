# Deepcopy API

Read-only API on an IBKR Client Portal gateway, built from the Deepcopy ADK
agent template (see [CLAUDE.md](CLAUDE.md) for the architecture and rules).

It never places, modifies or cancels orders. The gateway is started and signed
in by an operator; this API only reads from it.

## Layers

| Folder (`src/app/`) | Role |
| :------------------ | :--- |
| `clients/ibkr/` | `IbkrGatewayClient` contract (ABC) and its httpx implementation; gateway errors become `IbkrSessionError` / `IbkrGatewayError` |
| `dto/ibkr/` | Gateway responses as IBKR sends them (unknown fields ignored) |
| `mapper/` | IBKR DTOs to API responses |
| `dto/response/` | API responses |
| `services/` | Input validation and use cases; depends on the client contract only |
| `routes/`, `components/tools/` | FastAPI routes and ADK tools on top of the service |

## Routes

| Route | Purpose |
| :---- | :------ |
| `GET /ibkr/session` | Brokerage session status |
| `POST /ibkr/session/init` | Open the brokerage session without taking over another one |
| `GET /ibkr/accounts` | Portfolio accounts |
| `GET /ibkr/accounts/{account_id}/summary` | Account summary |
| `GET /ibkr/accounts/{account_id}/positions?page=0` | Account positions |
| `GET /ibkr/contracts?symbol=AAPL` | Contract search |

Errors use the template envelope: `IBKR_SESSION_ERROR` (503) when the gateway
is not signed in or the brokerage session is not open, `IBKR_GATEWAY_ERROR`
(502) otherwise. The ADK agent exposes the same reads as tools.

## Run locally

1. Start the gateway and sign in at https://localhost:5055:

   ```bash
   docker compose -f ../ibkr-gateway/compose.local.yml -p ibkr-gateway-local up -d --build
   ```

2. Run the API:

   ```bash
   just install
   cp .env.example .env   # set GOOGLE_CLOUD_PROJECT
   just api
   ```

3. If `/ibkr/session` reports `established: false`, call `POST /ibkr/session/init`.

## Quality

```bash
just pre-commit   # format + lint + tests
```
