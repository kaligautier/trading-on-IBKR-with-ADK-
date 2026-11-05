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
