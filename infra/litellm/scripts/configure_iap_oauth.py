"""Attach the console-created OAuth client to IAP without persisting secrets in state."""

import argparse
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "credentials",
        type=Path,
        help="Protected client JSON downloaded from Google Auth Platform",
    )
    parser.add_argument("--project", required=True)
    parser.add_argument("--project-number", required=True, type=int)
    parser.add_argument("--account", required=True)
    args = parser.parse_args()
    client = json.loads(args.credentials.read_text())["web"]
    if client.get("project_id") != args.project or not client["client_id"].startswith(
        f"{args.project_number}-"
    ):
        raise ValueError("OAuth client must belong to the selected project")
    token = subprocess.check_output(
        [
            "gcloud",
            "auth",
            "print-access-token",
            f"--account={args.account}",
        ],
        text=True,
    ).strip()
    url = f"https://iap.googleapis.com/v1/projects/{args.project_number}:iapSettings"
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        before = json.load(response)
    existing = before.get("accessSettings", {}).get("oauthSettings", {}).get("clientId")
    if existing and existing != client["client_id"]:
        raise ValueError(
            "A different OAuth client is already configured; explicit migration required"
        )
    payload = {
        "name": f"projects/{args.project_number}",
        "accessSettings": {
            "oauthSettings": {
                "clientId": client["client_id"],
                "clientSecret": client["client_secret"],
            }
        },
    }
    # Update only the client credentials, preserving every unrelated IAP setting.
    # https://docs.cloud.google.com/iap/docs/reference/rest/v1/TopLevel/updateIapSettings
    mask = "iapSettings.accessSettings.oauthSettings.clientId,iapSettings.accessSettings.oauthSettings.clientSecret"
    request = Request(
        url + "?updateMask=" + mask,
        headers=headers,
        data=json.dumps(payload).encode(),
        method="PATCH",
    )
    with urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result["accessSettings"]["oauthSettings"]["clientId"] != client["client_id"]:
        raise RuntimeError("IAP client verification failed")
    print(
        "IAP OAuth client configured and verified; credentials were not printed or stored in Terraform."
    )


if __name__ == "__main__":
    try:
        main()
    except HTTPError as error:
        print("IAP API failed:", error.code)
        raise SystemExit(1) from None
