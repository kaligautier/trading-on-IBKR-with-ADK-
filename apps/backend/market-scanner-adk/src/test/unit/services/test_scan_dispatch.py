"""Verify SDK submission without polling or overriding the configured Job."""

from unittest.mock import Mock

import pytest
from google.api_core.exceptions import DeadlineExceeded, PermissionDenied
from google.auth.exceptions import DefaultCredentialsError, RefreshError
from google.cloud import run_v2
from google.longrunning.operations_pb2 import Operation

from app.services import scan_dispatch
from app.utils.error import CloudRunError, InvalidInputError

JOB = "projects/test-project/locations/europe-west1/jobs/scanner"
OPERATION = "projects/test-project/locations/europe-west1/operations/accepted"


@pytest.mark.parametrize(
    "payload", [{"name": OPERATION}, {"name": OPERATION, "error": {"code": 7}}, {}]
)
def should_acknowledge_only_an_accepted_job_submission(payload):
    operation = Mock(operation=Operation(**payload))
    sdk = Mock(spec=run_v2.JobsClient)
    sdk.run_job.return_value = operation
    client = scan_dispatch.CloudRunJobsClient(JOB, client=sdk)
    if payload == {"name": OPERATION}:
        assert client.run_job() == OPERATION
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


@pytest.mark.parametrize("name", ["", "   ", "scanner", "projects/test/jobs/scanner"])
def should_reject_invalid_job_names_before_creating_a_client(monkeypatch, name):
    constructor = Mock()
    monkeypatch.setattr(scan_dispatch.run_v2.JobsClient, "__init__", constructor)
    with pytest.raises(InvalidInputError):
        scan_dispatch.CloudRunJobsClient(name)
    constructor.assert_not_called()


@pytest.mark.parametrize("failure", [PermissionDenied, DeadlineExceeded, RefreshError])
def should_translate_submission_errors_without_retrying_or_exposing_details(failure):
    error = failure("private provider details")
    sdk = Mock(spec=run_v2.JobsClient)
    sdk.run_job.side_effect = error
    with pytest.raises(CloudRunError) as raised:
        scan_dispatch.CloudRunJobsClient(JOB, client=sdk).run_job()
    assert raised.value.__cause__ is error
    assert raised.value.status_code == 502
    assert "private provider details" not in str(raised.value)
    sdk.run_job.assert_called_once()


def should_translate_client_initialization_errors(monkeypatch):
    monkeypatch.setattr(
        scan_dispatch.run_v2.JobsClient,
        "__init__",
        Mock(side_effect=DefaultCredentialsError("private credentials details")),
    )
    with pytest.raises(CloudRunError, match="initialize"):
        scan_dispatch.CloudRunJobsClient(JOB)


def should_reuse_the_lazy_client_for_the_configured_job(monkeypatch):
    constructor = Mock()
    monkeypatch.setattr(scan_dispatch, "CloudRunJobsClient", constructor)
    scan_dispatch.get_cloud_run_jobs_client.cache_clear()
    try:
        first = scan_dispatch.get_cloud_run_jobs_client(JOB)
        assert scan_dispatch.get_cloud_run_jobs_client(JOB) is first
        constructor.assert_called_once_with(JOB)
    finally:
        scan_dispatch.get_cloud_run_jobs_client.cache_clear()
