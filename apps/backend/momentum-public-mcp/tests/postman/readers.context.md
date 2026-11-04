# Momentum MCP reader simulation

Recorded 2026-10-27. Existing mock provenance and coverage are documented in
the service README under "Run and verify"; member handlers are in `mocks/`.

## Purpose

Exercise the real MCP application against the Momentum and Market Scanner
stand-ins defined in `readers.sim.yaml`, including the per-API client wiring.

## Execution

From the service directory, run `.venv/bin/python scripts/simulation.py`.
The script starts both servers, runs the saved collection, verifies traffic to
each simulation member and stops its process groups. Its temporary request log
is removed after the run.

## Assumptions

- 2026-10-27: Local execution succeeded with Postman CLI 1.73.0 without login;
  the CLI's cloud-publication warning did not prevent the local assertions.
- 2026-10-27: This run used simulated upstreams with IAM disabled by the script;
  it does not verify deployed IAM, real data or database persistence.

## Observations

<!-- begin:observations -->
- 2026-11-04: The recovered API/DTO/MCP refactor, rebased onto current main,
  passed 15 HTTP requests and 60 assertions. Both upstream mocks received
  real HTTP calls and required their distinct local bearer tokens. Six tools,
  the market scan resource, the static Markdown prompt, sanitized failures,
  and the delayed reader path passed. IAM and Cloud Trace export were disabled;
  this run does not establish deployed authentication or live export behavior.
- 2026-10-28: The simplified telemetry module (`init_telemetry`, `instrument_app`)
  with `ALWAYS_ON` and direct standard export passed 15 requests and 60 assertions.
  Both `momentum` and `scanner` received HTTP calls; no GCP export ran locally.
- 2026-10-28: The supplied `TraceInjectFilter`/python-json-logger pattern and
  telemetry-before-logging initialization in `main.py` passed 15 requests and
  60 assertions. Both upstream members received HTTP calls; startup/shutdown
  logs retained their messages with empty trace IDs outside an active span.
- 2026-10-28: After removing wide-event accumulation and its request-ID header,
  all 15 requests and 60 assertions passed. Both `momentum` and `scanner`
  received HTTP requests. Native OpenTelemetry spans and JSON logging remain;
  the service no longer emits a custom request-summary event.
- 2026-10-28: With the OpenTelemetry SDK enabled and Cloud Trace export disabled
  locally, 15 requests and 60 assertions passed. Both `momentum` and `scanner`
  received HTTP requests. Separate in-memory exporter tests verified ASGI/MCP/
  HTTPX span parentage, log correlation, error status and export redaction;
  this run does not establish live Cloud Trace ingestion.
- 2026-10-28: Structured application exceptions passed 15 HTTP requests and
  60 assertions. The simulated upstream failure returned a native MCP tool
  error containing `[MOMENTUM_API_ERROR]` without the upstream body. Both
  `momentum` and `scanner` received requests; IAM remained disabled locally.
- 2026-10-28: After removing the custom metadata middleware, all 15 requests
  and 59 assertions passed, including a direct analysis tool call without
  `clientInfo`. Both `momentum` and `scanner` received HTTP requests; no MCP
  session was created. The prompt now loads static Markdown instructions.
- 2026-10-28: With six tools, the market scan resource and the Jinja-backed
  `analyze_ticker` prompt, all 15 HTTP requests and 59 assertions passed.
  Both upstream simulation members received requests. Prompt rendering returned
  the normalized ticker and resource URI without unresolved template variables.
- 2026-10-27: After simplifying response DTOs and moving the gateway under
  `tools/`, the real MCP passed the simulation against both `momentum` and
  `scanner`; neither member stayed silent.
- 2026-10-27: After separating request/response DTOs, client configuration and
  service pagination, `scripts/simulation.py` passed again. Both `momentum` and
  `scanner` served requests; the write/status, failure and delayed paths passed.
- 2026-10-27: After separating the API clients, `scripts/simulation.py` passed.
  Both `momentum` and `scanner` served requests; neither member stayed silent.
  The write/status flow, sanitized upstream failure and delayed response passed.
<!-- end:observations -->

## What didn't work

- 2026-10-27: Moving settings into `config/config.py` left an old import in
  `application.py`, causing `ImportError: cannot import name 'Settings'` at
  startup. Updating that import restored the simulation.
- 2026-10-27: The sandbox rejected the initial socket bind with
  `PermissionError: [Errno 1] Operation not permitted`. The same command passed
  after authorization to run outside the sandbox.
