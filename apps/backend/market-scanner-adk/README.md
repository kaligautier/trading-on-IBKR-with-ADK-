# Market Scanner ADK HTTP operations

Job submission uses `POST /internal/v1/scan-jobs`. Authentication is unchanged:
Cloud Run IAM at ingress and the configured Scanner token at the application.
On upstream acceptance the response is 202 with `{ "status": "accepted",
"operation": "..." }` and `Cache-Control: no-store`. This acknowledges dispatch,
not successful completion of the scan. The operation identifier belongs to Cloud
Run; no unimplemented local polling URL is advertised. Submission bypasses the
worker admission lock because the worker obtains that lock when it executes.

Errors raised by this service, including authentication and admission failures,
follow [Google AIP-193](https://google.aip.dev/193): the body is a
`google.rpc.Status` in its HTTP/1.1+JSON form.

```json
{"error": {"code": 503, "message": "Scanner execution capacity is busy",
  "status": "UNAVAILABLE",
  "details": [
    {"@type": "type.googleapis.com/google.rpc.ErrorInfo",
     "reason": "SCANNER_BUSY", "domain": "market-scanner.deepcopy.fr",
     "metadata": {}},
    {"@type": "type.googleapis.com/google.rpc.RequestInfo",
     "requestId": "<X-Request-ID>"},
    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "30s"}]}}
```

`code` is the HTTP status, always the one of the canonical `status`, and
`ErrorInfo.reason` + `domain` the stable identifier clients branch on. Each
reason is an `ErrorCode` name from `src/app/utils/error.py`, which also maps it
to its HTTP status, canonical code and message. `AppError.kind` is technical for
`INTERNAL`, `UNAVAILABLE`, `UNKNOWN`, `DEADLINE_EXCEEDED` and `DATA_LOSS`, and a
domain (caller-resolvable) failure otherwise. Error details are logged, never
returned.

| Reason | Status | Canonical | When |
| --- | --- | --- | --- |
| `UNAUTHENTICATED` | 401 | `UNAUTHENTICATED` | Missing or invalid Scanner token |
| `SCANNER_BUSY` | 503 | `UNAVAILABLE` | Another database-backed run holds the admission lock (`Retry-After: 30`, `RetryInfo`) |
| `SCAN_JOB_NOT_CONFIGURED` | 503 | `UNAVAILABLE` | `MARKET_SCANNER_JOB` is not set |
| `SCAN_DISPATCH_FAILED` | 503 | `UNAVAILABLE` | Cloud Run did not accept the job execution |
| `LITELLM_ERROR`, `TOOL_EXECUTION_ERROR`, `MARKET_DATA_COLLECTION_ERROR` | 503 | `UNAVAILABLE` | An upstream dependency failed |

The old `/internal/daily-scan` path is removed. Update the Scheduler with this
release. GET does not dispatch work and returns 405 with `Allow: POST`.
SDK-owned ADK routes and `/health` retain their existing paths. The job runner,
financial/report contract and persistence are unchanged.

## Database execution admission

HTTP database-backed requests and scheduled jobs share a PostgreSQL advisory lock.
A competing HTTP request returns `503` with `Retry-After: 30` and
the `SCANNER_BUSY` Status above; WebSockets close with 1013.
A competing job emits `scheduled_scan.busy` and exits 75 without creating a session
or calling a model. Cloud Run retries remain disabled. Health and job dispatch do
not hold this lock; a dispatched job must still pass admission before running.
Authentication precedes admission. Result writes reuse the admitted connection;
ADK session connections close when returned so inactive revisions hold none.
Cancellation or process exit releases the lock. Apply the reviewed global role
budget and maintenance rollout procedure in `docs/database-connection-capacity.md`.
