"""Cloud Run Jobs client: submit executions of the daily Scanner Job."""

import logging
from typing import Optional

from google.api_core import exceptions as run_exceptions
from google.auth.exceptions import GoogleAuthError
from google.cloud import run_v2

from app.utils.error import CloudRunError, InvalidInputError

logger = logging.getLogger(__name__)


class CloudRunJobsClient:
    """Client bound to one Job whose execution configuration lives in Terraform."""

    def __init__(self, project_id: str, location: str, job_name: str):
        """Initialize the SDK client from the project's ID, region and Job name."""
        if not project_id or not project_id.strip():
            raise InvalidInputError(message="Project ID cannot be empty")
        if not location or not location.strip():
            raise InvalidInputError(message="Location cannot be empty")
        if not job_name or not job_name.strip():
            raise InvalidInputError(message="Job name cannot be empty")

        self._job_path = (
            f"projects/{project_id.strip()}/locations/{location.strip()}"
            f"/jobs/{job_name.strip()}"
        )

        try:
            self._client = run_v2.JobsClient()
        except (run_exceptions.GoogleAPIError, GoogleAuthError) as error:
            logger.error(
                "Failed to initialize Cloud Run Jobs client for %s (%s)",
                self._job_path,
                type(error).__name__,
            )
            raise CloudRunError(
                message="Failed to initialize Cloud Run Jobs client",
                details={"job_path": self._job_path},
            ) from error

        logger.debug("Initialized Cloud Run Jobs client for %s", self._job_path)

    def run_job(self) -> str:
        """Return the operation name on acceptance, without awaiting execution.

        The submission has a 30-second timeout and no automatic retry: an
        interrupted acknowledgement may still correspond to a running Job.
        """
        request = run_v2.RunJobRequest(name=self._job_path)

        try:
            operation = self._client.run_job(request=request, timeout=30, retry=None)
        except (run_exceptions.GoogleAPIError, GoogleAuthError) as error:
            logger.error(
                "Failed to trigger Cloud Run Job %s (%s)",
                self._job_path,
                type(error).__name__,
            )
            raise CloudRunError(
                message="Failed to trigger Cloud Run Job execution",
                details={"job_path": self._job_path},
            ) from error

        submitted = operation.operation
        if submitted.HasField("error") or not submitted.name:
            logger.error("Cloud Run did not accept Job %s", self._job_path)
            raise CloudRunError(message="Cloud Run did not accept the execution")

        operation_name = submitted.name
        logger.info(
            "Submitted Cloud Run Job %s (operation=%s)",
            self._job_path,
            operation_name,
            extra={"event": "scheduled_scan.accepted", "operation": operation_name},
        )
        return operation_name


# Singleton factory
_cloud_run_jobs_client: Optional[CloudRunJobsClient] = None


def get_cloud_run_jobs_client() -> CloudRunJobsClient:
    """Get the singleton client, lazily initialized from the configured Job."""
    global _cloud_run_jobs_client

    if _cloud_run_jobs_client is None:
        from app.config.settings import settings

        job = run_v2.JobsClient.parse_job_path(settings.MARKET_SCANNER_JOB.strip())
        if not job:
            raise InvalidInputError(message="A full Cloud Run Job name is required")
        _cloud_run_jobs_client = CloudRunJobsClient(
            project_id=job["project"],
            location=job["location"],
            job_name=job["job"],
        )

    return _cloud_run_jobs_client
