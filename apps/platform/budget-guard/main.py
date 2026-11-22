"""Budget kill switch: disable costly APIs once the budget is fully spent.

Triggered by Cloud Billing budget notifications published on Pub/Sub. It only
acts when ``costAmount >= budgetAmount`` and only on the services listed in the
SERVICES_TO_DISABLE environment variable of TARGET_PROJECT_ID. It is idempotent:
budget notifications repeat, and disabling an already disabled API is a no-op.
"""

import base64
import json
import logging
import os

import functions_framework
import google.auth
from google.auth.transport.requests import AuthorizedSession

SERVICE_USAGE = "https://serviceusage.googleapis.com/v1"
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def should_cut(notification: dict) -> bool:
    """True when the spend reached the budget; malformed payloads never cut."""
    try:
        return float(notification["costAmount"]) >= float(notification["budgetAmount"])
    except (KeyError, TypeError, ValueError):
        return False


def disable_service(session, project: str, service: str) -> None:
    # Without disableDependentServices the call fails instead of cascading to
    # other APIs, which keeps the blast radius to the listed services.
    response = session.post(
        f"{SERVICE_USAGE}/projects/{project}/services/{service}:disable",
        json={"disableDependentServices": False},
        timeout=30,
    )
    response.raise_for_status()
    logging.warning("Disabled %s on %s", service, project)


@functions_framework.cloud_event
def stop_spending(cloud_event):
    payload = cloud_event.data["message"]["data"]
    notification = json.loads(base64.b64decode(payload).decode("utf-8"))
    name = notification.get("budgetDisplayName", "unknown budget")
    if not should_cut(notification):
        logging.info(
            "%s: %s of %s %s, no action",
            name,
            notification.get("costAmount"),
            notification.get("budgetAmount"),
            notification.get("currencyCode", ""),
        )
        return
    project = os.environ["TARGET_PROJECT_ID"]
    services = [s for s in os.environ["SERVICES_TO_DISABLE"].split(",") if s]
    credentials, _ = google.auth.default(scopes=SCOPES)
    session = AuthorizedSession(credentials)
    errors = []
    for service in services:
        try:
            disable_service(session, project, service)
        except Exception:  # keep going so one failure does not leave others on
            logging.exception("Could not disable %s", service)
            errors.append(service)
    if errors:
        raise RuntimeError(f"Failed to disable: {', '.join(errors)}")
