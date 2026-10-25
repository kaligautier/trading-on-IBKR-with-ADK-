# Momentum public MCP

Migrated from `kaligautier/deep-copy-finary`, commit
`2f510084f777dea6c047375f22f291ba4a926a24`, directory
`apps/backend/momentum-public-mcp`. FastMCP and fastmcp-slim are pinned to
**4.1.3 (Root Awakening)**; `uv.lock` pins the complete runtime.

This backend exposes the original seven tool names over **POST /**. It invokes
the private Momentum consultation API and Market Scanner reader using separate
Cloud Run ID-token audiences. It has no database credentials or execution/admin
permissions. `/health` is a liveness probe, not proof of upstream availability.

## Stateless contract

The HTTP profile implements [SEP-2575](https://modelcontextprotocol.io/seps/2575-stateless-mcp)
using FastMCP's native `2026-07-28` transport:

- Each request is independent, including `tools/call` as the very first request.
- No `Mcp-Session-Id`, cookies, sticky sessions, shared session store or resumable
  event store. Every request carries its own client capabilities.
- `MCP-Protocol-Version` must match `params._meta["io.modelcontextprotocol/protocolVersion"]`.
- `clientInfo` (`name`, `version`) and `clientCapabilities` are required under
  the same namespaced `_meta`. A small HTTP validator retains SEP-2575's stricter
  clientInfo requirement: the newer SDK otherwise permits its absence.
- Legacy 2024/2025 protocol versions are rejected; they cannot re-enable an
  `initialize` handshake through FastMCP's backwards compatibility.
- Native `server/discover`, unsupported-version negotiation (`400`/`-32022`),
  and unknown/removed RPC errors (`404`/`-32601`) are tested on HTTP.
- `GET /` and `DELETE /` return 405. No standalone SSE channel is provided.
  This service exposes static tools, no subscriptions, sampling, elicitation,
  roots, background tasks or server log notifications. JSON responses suffice.
- Browser CORS permits public POSTs with the MCP headers, without credentials.

Use `Mcp-Method` (and `Mcp-Name` for a tool call), as required by the current
protocol's HTTP routing rules. The health endpoint alone uses GET.

```sh
curl "$MCP_URL/" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' -H 'Mcp-Name: list_analyses' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"list_analyses","arguments":{"limit":1},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientInfo":{"name":"curl","version":"1"},"io.modelcontextprotocol/clientCapabilities":{}}}}'
```

Always check `result.isError`, not just HTTP 200.

## Reader migration

The four Momentum tools use `/v1/analyses`, `/v1/analyses/latest`,
`/v1/analyses/{id}` and `/v1/recommendations`. Their public inputs and list output
shape (`structuredContent.result`) are retained. The adapter traverses the
reader's cursors to honor `limit`/`offset`, and fetches all latest pages rather
than silently dropping them. Repeated cursors fail, and the 45-second tool
deadline bounds traversal. Pagination does not create an MCP session.

`latest_market_scan` now returns the current reader envelope:
`{id, scan_date, created_at, report}`. `report` preserves the complete v3 data,
including decimal strings, null horizons and arbitration. Consumers of the old
flattened report must read `report.regime`, `report.summary`, `report.assets`.
The removed legacy `session_id` and `recommendation` fields are not fabricated.

## Suggestions through Momentum API

`suggest_ticker` and `get_suggestion_status` call `POST /suggestions` and
`GET /suggestions/{uuid}` on the same `MOMENTUM_API_URL` as the analysis tools,
with the same Cloud Run identity and original HMAC caller assertion. Validation,
quotas, persistence and moderation belong to Momentum API, as in DeepCopy.
The MCP has no storage adapter, database credentials or separate moderation URL.
It cannot approve a suggestion or start an analysis.

The recovered routes are deployed in Momentum API. A live public MCP submission,
status read and duplicate submission returned the same persisted pending record.
The API owns the PostgreSQL transaction, quotas and moderation fields.

## Run and verify

```sh
uv sync --frozen --python 3.12
uv run --frozen pytest -q
uv run --frozen ruff check src tests scripts
uv run --frozen ruff format --check src tests scripts
# With Postman CLI >=1.73.0 installed (no login or cloud publication):
uv run --frozen python scripts/simulation.py
```

The simulation runs this backend, not a mock of it. Its two local upstream
mocks derive from this repository's Momentum OpenAPI, Scanner producer v3
example/reader envelope, and the recovered DeepCopy suggestions contract. No
external owner's mock was needed: these are local services owned by this project.
The saved collection exercises all seven tools, a real HTTP write/status cycle
against the Momentum API mock, and a sanitized upstream failure. Unit tests also
cover separate IAM audiences and cursor traversal. Live IAM/data access needs
the deployed checks described in [Terraform](../../../infra/momentum-public-mcp/README.md).

`SUGGESTION_HASH_SECRET` is required for pseudonymization and moderation signing.
Never commit its value. `TRUSTED_PROXIES` is an explicit immediate-proxy CIDR
allowlist; by default forwarded addresses are not trusted. Rate limiting is a
best-effort 60 requests/minute per fingerprint **per replica**, not a distributed
quota. With no trusted proxy configured, callers sharing the direct peer share
that limit. It has no role in protocol session handling.

## Verification recorded on 2026-10-24

- 45 Python tests and Ruff checks passed.
- 45 Postman assertions passed over 12 real HTTP requests to the local MCP,
  including an upstream response delayed by 11 seconds.
- Three Terraform tests passed: public ingress/private reader grants, immutable
  image, and numeric secret-version constraints.
- Cloud Run revision `momentum-public-mcp-00003-7sx` receives 100% of traffic;
  Terraform reports no drift. Live requests reject all four 2024/2025 protocol
  versions and the removed `initialize`, `ping` and `logging/setLevel` methods.
- Live consultation returned AAPL analysis `9aee5d94-ce77-4ec9-bf02-5882eda66e02`
  and the 2026-10-24 Scanner report containing 25 assets, with no session headers.
  Both reader endpoints returned 403 without authentication.
- Live suggestion `3683f035-4525-4556-b761-df1e2ae2851c`
  (`MCPTEST-20261024-1230`) was created pending, read from a fresh HTTP request,
  and deduplicated to the same ID. An independent PostgreSQL read confirmed it.
  Its reason explicitly marks it as a verification fixture, not for approval.
- Momentum API revision `momentum-api-00003-g6c` handles suggestions using the
  existing one-connection pool. Its 261 tests passed with 95% branch-inclusive
  coverage; 33 Postman assertions exercised the real MCP/API/PostgreSQL chain,
  and 56 assertions passed against the exact release container image.
- These deployment checks preceded PR preparation; GitHub CI results are tracked
  separately on the dependent pull requests.
