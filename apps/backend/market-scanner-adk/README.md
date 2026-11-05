# Market Scanner ADK HTTP operations

Job submission uses `POST /internal/v1/scan-jobs`. Authentication is unchanged:
Cloud Run IAM at ingress and the configured Scanner token at the application.
On upstream acceptance the response is 202 with `{ "status": "accepted",
"operation": "..." }` and `Cache-Control: no-store`. This acknowledges dispatch,
not successful completion of the scan. The operation identifier belongs to Cloud
Run; no unimplemented local polling URL is advertised. Submission bypasses the
worker admission lock because the worker obtains that lock when it executes.

The old `/internal/daily-scan` path is removed. Update the Scheduler with this
release. GET does not dispatch work and returns 405 with `Allow: POST`.
SDK-owned ADK routes and `/health` retain their existing paths. The job runner,
financial/report contract and persistence are unchanged.

## Database execution admission

HTTP database-backed requests and scheduled jobs share a PostgreSQL advisory lock.
A competing HTTP request returns `503` with `Retry-After: 30` and
`{"detail":"Scanner execution capacity is busy"}`; WebSockets close with 1013.
A competing job emits `scheduled_scan.busy` and exits 75 without creating a session
or calling a model. Cloud Run retries remain disabled. Health and job dispatch do
not hold this lock; a dispatched job must still pass admission before running.
Authentication precedes admission. Result writes reuse the admitted connection;
ADK session connections close when returned so inactive revisions hold none.
Cancellation or process exit releases the lock. Apply the reviewed global role
budget and maintenance rollout procedure in `docs/database-connection-capacity.md`.
