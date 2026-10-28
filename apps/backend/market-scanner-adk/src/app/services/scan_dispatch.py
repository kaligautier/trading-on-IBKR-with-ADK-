"""Submit a Cloud Run execution; the worker owns the long-running scan."""

from functools import lru_cache

from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import GoogleAuthError
from google.cloud import run_v2

from app.utils.error import CloudRunError, InvalidInputError


class CloudRunJobsClient:
    """Submit executions of one Job using its Terraform-managed configuration."""

    def __init__(self, job_name: str, *, client: run_v2.JobsClient | None = None):
        """Bind to a full projects/.../locations/.../jobs/... resource name."""
        self._job_name = job_name.strip()
        if not run_v2.JobsClient.parse_job_path(self._job_name):
            raise InvalidInputError(message="A full Cloud Run Job name is required")
        try:
            self._client = client if client is not None else run_v2.JobsClient()
        except (GoogleAPIError, GoogleAuthError) as error:
            raise CloudRunError(
                message="Failed to initialize Cloud Run Jobs client",
                details={"job_name": self._job_name},
            ) from error

    def run_job(self) -> str:
        """Return the operation name on acceptance, without polling the execution.

        The submission has a 30-second timeout and no automatic retry: an
        interrupted acknowledgement may still correspond to a running Job.
        """
        try:
            operation = self._client.run_job(
                request=run_v2.RunJobRequest(name=self._job_name),
                timeout=30,
                retry=None,
            )
        except (GoogleAPIError, GoogleAuthError) as error:
            raise CloudRunError(
                message="Failed to trigger Cloud Run Job execution",
                details={"job_name": self._job_name},
            ) from error

        submitted = operation.operation
        if submitted.HasField("error") or not submitted.name:
            raise CloudRunError(message="Cloud Run did not accept the execution")
        return submitted.name


@lru_cache(maxsize=1)
def get_cloud_run_jobs_client(job_name: str) -> CloudRunJobsClient:
    """Lazily reuse the configured Job client within this process."""
    return CloudRunJobsClient(job_name)
