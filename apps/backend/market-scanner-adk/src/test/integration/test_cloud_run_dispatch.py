"""Exercise the route and real Google REST SDK against a local Postman mock."""

import os

import pytest
from fastapi.testclient import TestClient
from google.auth.credentials import AnonymousCredentials
from google.cloud import run_v2

from app import application
from app.services.scan_dispatch import CloudRunJobsClient

SIMULATION_URL = os.getenv("CLOUD_RUN_SIMULATION_URL")
pytestmark = pytest.mark.skipif(
    not SIMULATION_URL, reason="Start tests/postman/cloud-run.sim.yaml first"
)


@pytest.mark.parametrize(
    "job, status", [("accepted", 200), ("denied", 502), ("unavailable", 502)]
)
def should_submit_through_the_real_sdk_without_polling(monkeypatch, job, status):
    job_name = f"projects/test-project/locations/europe-west1/jobs/{job}"
    sdk = run_v2.JobsClient(
        transport="rest",
        credentials=AnonymousCredentials(),
        client_options={"api_endpoint": SIMULATION_URL},
    )
    sdk.transport._session.headers["x-mock-slug"] = "cloud-run"
    jobs_client = CloudRunJobsClient(job_name, client=sdk)
    monkeypatch.setattr(application.settings, "MARKET_SCANNER_TOKEN", "test-token")
    monkeypatch.setattr(application.settings, "MARKET_SCANNER_JOB", job_name)
    monkeypatch.setattr(
        application.settings, "DATABASE_URL", "postgresql://unused@127.0.0.1/scanner"
    )
    monkeypatch.setattr(application, "get_cloud_run_jobs_client", lambda _: jobs_client)
    # Submission does not use sessions; omit the database-checking lifespan here.
    client = TestClient(application.create_app())
    try:
        response = client.post(
            "/internal/daily-scan", headers={"X-Market-Scanner-Token": "test-token"}
        )
        assert response.status_code == status
        expected = (
            {
                "status": "accepted",
                "operation": (
                    "projects/test-project/locations/europe-west1/operations/submitted"
                ),
            }
            if status == 200
            else {"detail": "Scheduled scan dispatch failed"}
        )
        assert response.json() == expected
    finally:
        client.close()
        sdk.transport.close()
