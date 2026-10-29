# Market Scanner Job submission

The scheduled `POST /internal/daily-scan` route uses `CloudRunJobsClient` in
`app.services.scan_dispatch` to submit the configured `MARKET_SCANNER_JOB` through
the Google Cloud Run v2 SDK. An explicit module singleton reuses the client in each process.
The no-argument `get_cloud_run_jobs_client()` factory reads settings and extracts
project, region and short Job name from `MARKET_SCANNER_JOB`, then constructs
`CloudRunJobsClient(project_id, location, job_name)`. The model's project and
location are not used to select the Job. The class owns SDK creation and logs
initialization, submission acceptance and failures without provider error text.
Client initialization and submission run in worker threads, outside the HTTP
server's event loop.

The route returns HTTP 200 with `status: accepted` and the **operation name**,
without polling or waiting for the scan. Missing configuration returns 503;
initialization or submission failures return 502 without provider details.
Submission uses a 30-second timeout and disables automatic retries because a lost
acknowledgement may still correspond to a running execution. Job task count,
environment, timeout and worker retries remain managed by Terraform; no execution
overrides or additional IAM permissions are needed.

The Job runs `app.jobs.daily_scan`: ADK executes the workflow and persists the
report before exiting. Submission acceptance does not establish scan success.

## Local verification

From this directory:

```sh
uv sync --frozen --dev --python 3.12
uv run --frozen pytest -q src/test/unit
uv run --frozen ruff check src
uv run --frozen ruff format --check src/app
```

See [the Cloud Run simulation](tests/postman/cloud-run.context.md) for the real
SDK HTTP contract check, including upstream 403 and 503 responses.
