"""Submit a Cloud Run execution; the worker owns the long-running scan."""

import google.auth
from google.auth.transport.requests import AuthorizedSession


def dispatch_scan(job_name: str) -> str:
    """Return the operation name after acceptance, never wait for completion."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    with AuthorizedSession(credentials) as client:
        response = client.post(
            f"https://run.googleapis.com/v2/{job_name}:run", json={}, timeout=30
        )
        response.raise_for_status()
        operation = response.json()
    if operation.get("error") or not operation.get("name"):
        raise RuntimeError("Cloud Run did not accept the execution")
    return operation["name"]
