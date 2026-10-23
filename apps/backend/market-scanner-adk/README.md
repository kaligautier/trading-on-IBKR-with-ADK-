
### Database execution admission

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
