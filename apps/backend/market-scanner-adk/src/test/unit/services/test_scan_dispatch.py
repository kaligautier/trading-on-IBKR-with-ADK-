"""Verify SDK submission without polling or overriding the configured Job."""

import logging
from unittest.mock import Mock

import pytest
from google.api_core.exceptions import DeadlineExceeded, PermissionDenied
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.cloud import run_v2
from google.longrunning.operations_pb2 import Operation

from app.config.settings import settings
from app.services import scan_dispatch
from app.utils.error import CloudRunError, InvalidInputError

JOB = "projects/test-project/locations/europe-west1/jobs/scanner"
OPERATION = "projects/test-project/locations/europe-west1/operations/accepted"


@pytest.mark.parametrize(
    "payload", [{"name": OPERATION}, {"name": OPERATION, "error": {"code": 7}}, {}]
)
def should_acknowledge_only_an_accepted_job_submission(monkeypatch, caplog, payload):
    operation = Mock(operation=Operation(**payload))
    sdk = Mock(spec=run_v2.JobsClient)
    sdk.run_job.return_value = operation
    monkeypatch.setattr(scan_dispatch.run_v2, "JobsClient", Mock(return_value=sdk))
    caplog.set_level(logging.DEBUG, logger=scan_dispatch.__name__)
    client = scan_dispatch.CloudRunJobsClient("test-project", "europe-west1", "scanner")
    if payload == {"name": OPERATION}:
        assert client.run_job() == OPERATION
        assert OPERATION in caplog.text
        assert JOB in caplog.text
    else:
        with pytest.raises(CloudRunError, match="did not accept"):
            client.run_job()
    sdk.run_job.assert_called_once_with(
        request=run_v2.RunJobRequest(name=JOB), timeout=30, retry=None
    )
    request = sdk.run_job.call_args.kwargs["request"]
    assert not run_v2.RunJobRequest.pb(request).HasField("overrides")
    operation.result.assert_not_called()
    operation.done.assert_not_called()
    operation.exception.assert_not_called()


@pytest.mark.parametrize("field", ["project_id", "location", "job_name"])
@pytest.mark.parametrize("value", ["", "   ", None])
def should_reject_empty_settings_before_creating_a_client(monkeypatch, field, value):
    constructor = Mock()
    monkeypatch.setattr(scan_dispatch.run_v2, "JobsClient", constructor)
    arguments = {
        "project_id": "test-project",
        "location": "europe-west1",
        "job_name": "scanner",
    }
    arguments[field] = value
    with pytest.raises(InvalidInputError):
        scan_dispatch.CloudRunJobsClient(**arguments)
    constructor.assert_not_called()


@pytest.mark.parametrize("failure", [PermissionDenied, DeadlineExceeded, RefreshError])
def should_translate_submission_errors_without_retrying_or_exposing_details(
    monkeypatch, caplog, failure
):
    error = failure("private provider details")
    sdk = Mock(spec=run_v2.JobsClient)
    sdk.run_job.side_effect = error
    monkeypatch.setattr(scan_dispatch.run_v2, "JobsClient", Mock(return_value=sdk))
    with pytest.raises(CloudRunError) as raised:
        scan_dispatch.CloudRunJobsClient(
            "test-project", "europe-west1", "scanner"
        ).run_job()
    assert raised.value.__cause__ is error
    assert raised.value.status_code == 502
    assert "private provider details" not in str(raised.value)
    sdk.run_job.assert_called_once()
    assert "private provider details" not in caplog.text
    assert JOB in caplog.text


def should_translate_client_initialization_errors(monkeypatch):
    monkeypatch.setattr(
        scan_dispatch.run_v2.JobsClient,
        "__init__",
        Mock(side_effect=DefaultCredentialsError("private credentials details")),
    )
    with pytest.raises(CloudRunError, match="initialize"):
        scan_dispatch.CloudRunJobsClient("test-project", "europe-west1", "scanner")


def should_initialize_the_singleton_from_settings_once(monkeypatch):
    constructor = Mock()
    monkeypatch.setattr(scan_dispatch, "CloudRunJobsClient", constructor)
    monkeypatch.setattr(scan_dispatch, "_cloud_run_jobs_client", None)
    monkeypatch.setattr(settings, "MARKET_SCANNER_JOB", JOB)
    # The model region must never become the Cloud Run Job region.
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_LOCATION", "global")
    monkeypatch.setattr(settings, "GOOGLE_CLOUD_PROJECT", "model-project")
    first = scan_dispatch.get_cloud_run_jobs_client()
    assert scan_dispatch.get_cloud_run_jobs_client() is first
    constructor.assert_called_once_with(
        project_id="test-project", location="europe-west1", job_name="scanner"
    )


@pytest.mark.parametrize("job", ["", "scanner", "projects/test/jobs/scanner"])
def should_reject_malformed_job_settings_before_initializing(monkeypatch, job):
    constructor = Mock()
    monkeypatch.setattr(scan_dispatch, "CloudRunJobsClient", constructor)
    monkeypatch.setattr(scan_dispatch, "_cloud_run_jobs_client", None)
    monkeypatch.setattr(settings, "MARKET_SCANNER_JOB", job)
    with pytest.raises(InvalidInputError):
        scan_dispatch.get_cloud_run_jobs_client()
    constructor.assert_not_called()


def should_allow_initialization_after_a_failed_attempt(monkeypatch):
    constructor = Mock(side_effect=[CloudRunError(), Mock()])
    monkeypatch.setattr(scan_dispatch, "CloudRunJobsClient", constructor)
    monkeypatch.setattr(scan_dispatch, "_cloud_run_jobs_client", None)
    monkeypatch.setattr(settings, "MARKET_SCANNER_JOB", JOB)
    with pytest.raises(CloudRunError):
        scan_dispatch.get_cloud_run_jobs_client()
    assert scan_dispatch._cloud_run_jobs_client is None
    assert scan_dispatch.get_cloud_run_jobs_client() is not None
    assert constructor.call_count == 2
