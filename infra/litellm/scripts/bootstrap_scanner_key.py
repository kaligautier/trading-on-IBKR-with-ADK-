"""Provision a private-gateway client key from a VPC-attached bootstrap job.

The job mounts the master key from Secret Manager. Agents receive only their
inference key and never authenticate through IAP. No credential is printed.
"""

import base64
import os
from uuid import uuid4

import google.auth
from google.auth.transport.requests import Request
import httpx

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
BASE_URL = os.environ.get("LITELLM_BASE_URL", "").rstrip("/")
SECRET = os.environ.get("LITELLM_CLIENT_SECRET", "litellm-client-market-scanner-adk")
MODELS = os.environ.get("LITELLM_MODELS", "gemini-3.8-flash").split(",")


class BootstrapError(RuntimeError):
    """Safe operation names and HTTP codes, never upstream response bodies."""


def validate_configuration():
    if not PROJECT:
        raise ValueError("Set GOOGLE_CLOUD_PROJECT")
    url = httpx.URL(BASE_URL)
    if (
        url.scheme != "https"
        or not url.host
        or url.userinfo
        or url.path != "/"
        or url.query
        or url.fragment
    ):
        raise ValueError("LITELLM_BASE_URL must be an HTTPS origin without credentials")


def secret_request(client, credentials, method, path, **kwargs):
    credentials.refresh(Request())
    response = client.request(
        method,
        f"https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets/{SECRET}{path}",
        headers={"Authorization": f"Bearer {credentials.token}"},
        **kwargs,
    )
    if response.status_code != 200:
        raise BootstrapError(
            f"Secret Manager request failed (HTTP {response.status_code})"
        )
    return response.json()


def main():
    validate_configuration()
    master = os.environ.get("LITELLM_MASTER_KEY")
    if not master:
        raise ValueError("Mount LITELLM_MASTER_KEY from Secret Manager")
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    with httpx.Client(timeout=60, follow_redirects=False) as cloud:
        existing = secret_request(
            cloud, credentials, "GET", "/versions", params={"filter": "state:ENABLED"}
        ).get("versions", [])
        if existing:
            print("Existing client secret version:", existing[0]["name"].split("/")[-1])
            return
        with httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": "Bearer " + master},
            timeout=60,
            follow_redirects=False,
        ) as proxy:
            response = proxy.post(
                "/key/generate",
                json={
                    # Preserve keys retained in a recovered database: aliases are unique.
                    "key_alias": SECRET.removeprefix("litellm-client-")
                    + "-"
                    + uuid4().hex[:12],
                    "models": MODELS,
                    "allowed_routes": ["/v1beta/models/*"],
                    "duration": "30d",
                    "max_budget": 10,
                    "budget_duration": "30d",
                    "rpm_limit": 10,
                    "tpm_limit": 100000,
                    "max_parallel_requests": 2,
                    "metadata": {"authentication": "private-network-virtual-key"},
                },
            )
            if response.status_code != 200:
                raise BootstrapError(
                    f"Key creation failed (HTTP {response.status_code})"
                )
            result = response.json()
            key = result["key"]
            try:
                uploaded = secret_request(
                    cloud,
                    credentials,
                    "POST",
                    ":addVersion",
                    json={"payload": {"data": base64.b64encode(key.encode()).decode()}},
                )
            except Exception:
                cleanup = proxy.post("/key/delete", json={"keys": [key]})
                if cleanup.status_code != 200:
                    raise BootstrapError(
                        "Upload and cleanup failed; revoke the client key"
                    ) from None
                raise
        print("Client secret version:", uploaded["name"].split("/")[-1])
        print("Key expires:", result.get("expires"))
        print("Allowed models:", ", ".join(MODELS))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if isinstance(error, BootstrapError):
            print(str(error))
        print(
            f"Bootstrap stopped ({type(error).__name__}); credential details suppressed"
        )
        raise SystemExit(1) from None
