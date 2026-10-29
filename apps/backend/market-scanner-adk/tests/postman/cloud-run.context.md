# Scanner Cloud Run submission simulation

Created 2026-10-28 from the official
[jobs.run contract](https://docs.cloud.google.com/run/docs/reference/rest/v2/projects.locations.jobs/run).
The owner's mock search was unavailable because the Postman CLI was signed out.
Orbit discovery failed certificate validation; the Google contract was used directly.

## Purpose

Exercise the actual ASGI submission route, application client and Google REST SDK
against a local Cloud Run substitute. It models acceptance with an unfinished
operation and upstream 403/503 errors. Unexpected paths, including polling, fail.

## Execution

From `apps/backend/market-scanner-adk`, start in one terminal:

```sh
postman simulation run tests/postman/cloud-run.sim.yaml --port 4937 --output ndjson --no-history
```

After the `listening` event, run in another terminal:

```sh
CLOUD_RUN_SIMULATION_URL=http://127.0.0.1:4937 uv run --frozen pytest -q src/test/integration/test_cloud_run_dispatch.py
```

Expect three passing cases and exactly three `POST` request events with empty
bodies, status codes 200/403/503 and no polling. Stop the simulation with Ctrl-C.

## Assumptions

- 2026-10-28: the test injects an anonymous REST SDK client and a local endpoint;
  it does not verify real Google IAM, credentials, the default gRPC transport or
  execution of the worker.
- 2026-10-28: the ASGI test omits the PostgreSQL-checking lifespan. The submission
  route does not use sessions; database startup and persistence have separate tests.
- The mock accepts only test-project resources and never forwards to Google.

## Observations

<!-- begin:observations -->
- 2026-10-29: the no-argument settings factory and explicit singleton passed all
  three cases through the real REST SDK. The sole member `cloud-run` served
  exactly three POST requests (200/403/503), with no polling or retries; no
  member was silent. The class constructs its SDK client internally.
- 2026-10-28: all three HTTP cases passed. The sole member `cloud-run` served
  three requests with empty JSON bodies; no member was silent. An unfinished
  operation returned immediately, upstream errors became sanitized HTTP 502,
  and neither retries nor polling appeared in the request log.
<!-- end:observations -->

## What didn't work

- 2026-10-28: the first ASGI run stopped before submission because application
  startup required a PostgreSQL session store. The focused test now supplies a
  syntactically valid local database URL and omits the unrelated lifespan.
