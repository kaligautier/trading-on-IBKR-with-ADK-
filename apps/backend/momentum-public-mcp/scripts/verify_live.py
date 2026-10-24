"""Verify the deployed stateless HTTP contract and real consultation results.

Read-only by default. --suggestion-symbol explicitly exercises pending intake.
"""

import argparse
import json
import urllib.error
import urllib.request
from uuid import UUID

VERSION = "2026-07-28"
PREFIX = "io.modelcontextprotocol/"


def rpc(url, method, params=None, *, version=VERSION, expected_status=200):
    params = params or {}
    body = {
        "jsonrpc": "2.0",
        "id": "independent",
        "method": method,
        "params": {
            "_meta": {
                PREFIX + "protocolVersion": version,
                PREFIX + "clientInfo": {"name": "live-verifier", "version": "1"},
                PREFIX + "clientCapabilities": {},
            },
            **params,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": version,
        "Mcp-Method": method,
    }
    if params.get("name"):
        headers["Mcp-Name"] = params["name"]
    request = urllib.request.Request(url, json.dumps(body).encode(), headers)
    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        assert response.status == expected_status, response.status
        assert not response.headers.get("Mcp-Session-Id")
        assert not response.headers.get("Set-Cookie")
        UUID(response.headers["X-Request-ID"])
        payload = json.load(response)
    if expected_status != 200:
        return payload["error"]
    assert "error" not in payload, payload
    return payload["result"]


def tool(url, name, arguments):
    result = rpc(url, "tools/call", {"name": name, "arguments": arguments})
    assert not result.get("isError"), result
    return result["structuredContent"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--suggestion-symbol")
    args = parser.parse_args()
    url = args.url.rstrip("/") + "/"
    # First ever request is a business call; no discover/initialize/cookies.
    summaries = tool(url, "list_analyses", {"limit": 1})["result"]
    assert summaries, "No persisted analysis available to verify get_analysis"
    detail = tool(url, "get_analysis", {"analysis_id": summaries[0]["id"]})
    assert detail["id"] == summaries[0]["id"]
    assert detail["ticker"] == summaries[0]["ticker"]
    assert "portfolio_decision" in detail and "technical_indicators" in detail
    latest = tool(url, "latest_analyses", {"ticker": summaries[0]["ticker"]})["result"]
    assert len(latest) == 1
    recommendations = tool(url, "get_recommendations", {"limit": 1})["result"]
    assert all(item["rating"] in {"Buy", "Overweight"} for item in recommendations)
    scan = tool(url, "latest_market_scan", {})
    assert scan["report"]["schema_version"] == 3
    assert scan["report"]["assets"]
    discovery = rpc(url, "server/discover")
    assert VERSION in discovery["supportedVersions"]
    tools = rpc(url, "tools/list")["tools"]
    assert {item["name"] for item in tools} == {
        "list_analyses",
        "latest_analyses",
        "get_analysis",
        "get_recommendations",
        "latest_market_scan",
        "suggest_ticker",
        "get_suggestion_status",
    }
    for version in ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25"):
        error = rpc(
            url,
            "initialize",
            {
                "protocolVersion": version,
                "capabilities": {},
                "clientInfo": {"name": "legacy-probe", "version": "1"},
            },
            version=version,
            expected_status=400,
        )
        assert error["code"] == -32022
        assert error["data"]["supported"] == [VERSION]
    for method in ("initialize", "ping", "logging/setLevel"):
        assert rpc(url, method, expected_status=404)["code"] == -32601

    suggestion_check = "not exercised (read-only verification)"
    if args.suggestion_symbol:
        submitted = tool(
            url,
            "suggest_ticker",
            {
                "symbol": args.suggestion_symbol,
                "reason": "MCP migration verification; test only, do not approve.",
            },
        )
        assert submitted["status"] == "pending"
        identifier = submitted["id"]
        reread = tool(url, "get_suggestion_status", {"suggestion_id": identifier})
        assert reread["id"] == identifier and reread["status"] == "pending"
        repeated = tool(url, "suggest_ticker", {"symbol": args.suggestion_symbol})
        assert repeated["id"] == identifier
        suggestion_check = {
            "id": identifier,
            "symbol": args.suggestion_symbol,
            "status": "pending",
            "duplicate_same_id": True,
        }
    print(
        json.dumps(
            {
                "url": url,
                "protocol": VERSION,
                "tools": sorted(item["name"] for item in tools),
                "analysis_id": detail["id"],
                "ticker": detail["ticker"],
                "scan_id": scan["id"],
                "scan_date": scan["scan_date"],
                "assets": len(scan["report"]["assets"]),
                "session_headers": False,
                "correlation_headers": True,
                "legacy_handshake": "rejected for all four legacy versions",
                "suggestions": suggestion_check,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
