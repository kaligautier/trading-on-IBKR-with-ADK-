# Market Scanner ADK HTTP operations

Job submission uses `POST /internal/v1/scan-jobs`. Authentication is unchanged:
Cloud Run IAM at ingress and the configured Scanner token at the application.
On upstream acceptance the response is 202 with `{ "status": "accepted",
"operation": "..." }` and `Cache-Control: no-store`. This acknowledges dispatch,
not successful completion of the scan. The operation identifier belongs to Cloud
Run; no unimplemented local polling URL is advertised. Submission bypasses the
worker admission lock because the worker obtains that lock when it executes.

Errors raised by this service, including authentication and admission failures,
use one envelope: `{"error": {"code": "...", "message": "..."}}`. Each code is an
`ErrorCode` name from `src/app/utils/error.py`, which also maps it to its HTTP
status and message. Error details are logged, never returned.

| Code | Status | When |
| --- | --- | --- |
| `UNAUTHENTICATED` | 401 | Missing or invalid Scanner token |
| `SCANNER_BUSY` | 503 | Another database-backed run holds the admission lock |
| `SCAN_JOB_NOT_CONFIGURED` | 503 | `MARKET_SCANNER_JOB` is not set |
| `SCAN_DISPATCH_FAILED` | 502 | Cloud Run did not accept the job execution |

The old `/internal/daily-scan` path is removed. Update the Scheduler with this
release. GET does not dispatch work and returns 405 with `Allow: POST`.
SDK-owned ADK routes and `/health` retain their existing paths. The job runner,
financial/report contract and persistence are unchanged.

## Database execution admission

HTTP database-backed requests and scheduled jobs share a PostgreSQL advisory lock.
A competing HTTP request returns `503` with `Retry-After: 30` and
`{"error":{"code":"SCANNER_BUSY","message":"Scanner execution capacity is busy"}}`; WebSockets close with 1013.
A competing job emits `scheduled_scan.busy` and exits 75 without creating a session
or calling a model. Cloud Run retries remain disabled. Health and job dispatch do
not hold this lock; a dispatched job must still pass admission before running.
Authentication precedes admission. Result writes reuse the admitted connection;
ADK session connections close when returned so inactive revisions hold none.
Cancellation or process exit releases the lock. Apply the reviewed global role
budget and maintenance rollout procedure in `docs/database-connection-capacity.md`.
