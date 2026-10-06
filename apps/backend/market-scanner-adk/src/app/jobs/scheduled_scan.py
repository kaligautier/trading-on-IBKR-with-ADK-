"""Run a complete daily scan through the existing ADK HTTP contract."""

import json
from uuid import uuid4

import httpx


class ScheduledScanError(Exception):
    """A scheduled run did not produce a persisted report."""


async def run_scheduled_scan(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> dict[str, str | int]:
    """Create a UUID session, consume run_sse, and require persistence proof."""
    session_id = str(uuid4())
    marker = f"scheduled:{session_id}"
    session = await client.post(
        "/apps/market_scanner/users/scheduler/sessions",
        headers=headers,
        json={"session_id": session_id, "state": {"session_id": marker}},
    )
    session.raise_for_status()
    if session.json().get("id") != session_id:
        raise ScheduledScanError("ADK returned a different session ID")

    result = None
    async with client.stream(
        "POST",
        "/run_sse",
        headers=headers,
        json={
            "appName": "market_scanner",
            "userId": "scheduler",
            "sessionId": session_id,
            "newMessage": {
                "role": "user",
                "parts": [{"text": "Run the complete daily market scan."}],
            },
            "streaming": False,
        },
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue
            event = json.loads(line[5:].strip())
            if event.get("errorCode") or event.get("error"):
                raise ScheduledScanError("ADK emitted an SSE error event")
            path = event.get("nodeInfo", {}).get("path", "")
            node_name = path.rsplit("/", 1)[-1].split("@", 1)[0]
            if node_name == "persist_market_scan":
                report = event.get("output", {}).get("market_regime")
                if isinstance(report, dict) and report.get("assets"):
                    result = {
                        "session_id": session_id,
                        "marker": marker,
                        "assets": len(report["assets"]),
                    }
    if result is None:
        raise ScheduledScanError("ADK ended without a persisted report event")
    return result
