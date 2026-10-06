"""Verify job submission without waiting for the remote execution."""

from unittest.mock import Mock

import pytest

from app.services import scan_dispatch


@pytest.mark.parametrize(
    "payload", [{"name": "operations/accepted"}, {"error": {"code": 7}}, {}]
)
def should_acknowledge_only_an_accepted_job_submission(monkeypatch, payload):
    credentials = Mock()
    monkeypatch.setattr(
        scan_dispatch.google.auth, "default", Mock(return_value=(credentials, None))
    )
    client = Mock()
    client.post.return_value.json.return_value = payload
    session = Mock()
    session.__enter__ = Mock(return_value=client)
    session.__exit__ = Mock(return_value=False)
    factory = Mock(return_value=session)
    monkeypatch.setattr(scan_dispatch, "AuthorizedSession", factory)
    job = "projects/test-project/locations/europe-west1/jobs/scanner"
    if "name" in payload:
        assert scan_dispatch.dispatch_scan(job) == payload["name"]
    else:
        with pytest.raises(RuntimeError, match="did not accept"):
            scan_dispatch.dispatch_scan(job)
    client.post.assert_called_once_with(
        f"https://run.googleapis.com/v2/{job}:run", json={}, timeout=30
    )
    client.post.return_value.raise_for_status.assert_called_once()
    client.get.assert_not_called()
