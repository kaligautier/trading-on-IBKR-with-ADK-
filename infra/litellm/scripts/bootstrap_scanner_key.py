"""Create a scoped scanner key and store it without exposing credential values.

Apply clients.tf first. Run with the backend Python environment (httpx).
Existing secret versions are reused; rotation must be an explicit operation.
"""

import json
import os
import subprocess
import time

import httpx

ACCOUNT = os.environ.get("LITELLM_GCP_ACCOUNT", "")
PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
BASE_URL = os.environ.get("LITELLM_BASE_URL", "").rstrip("/")
SERVICE_ACCOUNT = f"market-scanner-adk@{PROJECT}.iam.gserviceaccount.com"
SECRET = "litellm-client-market-scanner-adk"
MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]


def validate_configuration():
    if not ACCOUNT or not PROJECT:
        raise ValueError("Set LITELLM_GCP_ACCOUNT and GOOGLE_CLOUD_PROJECT")
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


def gcloud(*args, data=None):
    result = subprocess.run(
        ["gcloud", *args, f"--project={PROJECT}", f"--account={ACCOUNT}"],
        input=data,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError(f"gcloud {args[0]} {args[1]} failed")
    return result.stdout.strip()


def iap_headers(key):
    token = gcloud("auth", "print-access-token")
    now = int(time.time())
    response = httpx.post(
        "https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/"
        f"{SERVICE_ACCOUNT}:signJwt",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "payload": json.dumps(
                {
                    "iss": SERVICE_ACCOUNT,
                    "sub": SERVICE_ACCOUNT,
                    "aud": BASE_URL + "/*",
                    "iat": now,
                    "exp": now + 600,
                }
            )
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"IAM signing failed (HTTP {response.status_code})")
    return {
        "Proxy-Authorization": "Bearer " + response.json()["signedJwt"],
        "Authorization": "Bearer " + key,
    }


def main():
    validate_configuration()
    existing = json.loads(
        gcloud(
            "secrets",
            "versions",
            "list",
            SECRET,
            "--format=json",
            "--filter=state=ENABLED",
            "--sort-by=~createTime",
            "--limit=1",
        )
    )
    if existing:
        print("Existing client secret version:", existing[0]["name"].split("/")[-1])
        return
    master = gcloud(
        "secrets", "versions", "access", "latest", "--secret=litellm-master-key"
    )
    headers = iap_headers(master)
    with httpx.Client(base_url=BASE_URL, headers=headers, timeout=60) as client:
        response = client.post(
            "/key/generate",
            json={
                "key_alias": "market-scanner-adk",
                "models": MODELS,
                "allowed_routes": ["/v1beta/models/*"],
                "duration": "30d",
                "max_budget": 10,
                "budget_duration": "30d",
                "rpm_limit": 10,
                "tpm_limit": 100000,
                "max_parallel_requests": 2,
                "metadata": {"application": "market-scanner-adk", "auth": "gcp-iap-sa"},
            },
        )
        if response.status_code != 200:
            raise RuntimeError(f"Key creation failed (HTTP {response.status_code})")
        result = response.json()
        key = result["key"]
        try:
            version = gcloud(
                "secrets",
                "versions",
                "add",
                SECRET,
                "--data-file=-",
                "--format=value(name)",
                data=key,
            ).split("/")[-1]
        except Exception:
            rollback = client.post("/key/delete", json={"keys": [key]})
            if rollback.status_code != 200:
                raise RuntimeError(
                    "Secret upload and key cleanup failed; revoke the scanner key in LiteLLM"
                ) from None
            raise
    print("Client secret version:", version)
    print("Key expires:", result.get("expires"))
    print("Allowed models:", ", ".join(MODELS))


if __name__ == "__main__":
    main()
