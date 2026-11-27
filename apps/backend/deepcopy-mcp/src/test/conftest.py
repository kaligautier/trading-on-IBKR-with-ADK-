"""Keep local developer configuration out of deterministic tests."""

import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from app.config.settings import Settings

TOKEN = "deepcopy-test-token"
SESSION = {
    "authenticated": True,
    "established": True,
    "competing": False,
    "connected": True,
    "message": "",
}
ACCOUNT = {
    "account_id": "U1234567",
    "title": "Test account",
    "display_name": "U1234567",
    "currency": "EUR",
    "account_type": "INDIVIDUAL",
}
POSITION = {
    "conid": 265598,
    "symbol": "AAPL",
    "asset_class": "STK",
    "quantity": 3,
    "market_price": 190.5,
    "market_value": 571.5,
    "average_cost": 150,
    "unrealized_pnl": 121.5,
    "currency": "USD",
}
CONTRACT = {
    "conid": 265598,
    "symbol": "AAPL",
    "company_name": "APPLE INC",
    "exchange": "NASDAQ",
    "security_types": ["STK", "OPT"],
}
FAILURES = {
    "MISSING": 404,
    "AUTH": 401,
    "FORBIDDEN": 403,
    "BADINPUT": 400,
    "LIMITED": 429,
    "DOWN": 503,
    "REDIRECT": 302,
}


def summary(account_id: str) -> dict:
    return {
        "account_id": account_id,
        "currency": "EUR",
        "net_liquidation": 1000.0,
        "total_cash": 250.0,
        "buying_power": 4000.0,
        "available_funds": 250.0,
        "gross_position_value": None,
    }


def route(path: str) -> tuple[str, int, object]:
    """Return the failure key, status and payload of one /ibkr request."""
    url = urlsplit(path)
    parts = url.path.strip("/").split("/")
    if parts == ["v1", "ibkr", "session"]:
        return "", 200, SESSION
    if parts == ["v1", "ibkr", "accounts"]:
        return "", 200, [ACCOUNT]
    if parts[:3] == ["v1", "ibkr", "accounts"] and len(parts) == 5:
        key = parts[3]
        return key, 200, summary(key) if parts[4] == "summary" else [POSITION]
    if parts == ["v1", "ibkr", "contracts"]:
        key = parse_qs(url.query).get("symbol", [""])[0]
        return key, 200, [CONTRACT | {"symbol": key}]
    return "", 501, {}


def misbehave(key: str, status: int, payload: object) -> tuple[int, dict, bytes]:
    """Apply the failure mode selected by an account ID or symbol."""
    headers: dict[str, str] = {}
    if key in FAILURES:
        status = FAILURES[key]
        headers["Location"] = "/v1/ibkr/accounts"
        payload = {"secret": "private-backend-detail"}
    elif key == "INVALID":
        payload = {"account_id": key, "net_liquidation": "lots"}
    elif key == "WRONG":
        payload = summary("OTHER")
    elif key == "SLOW":
        time.sleep(0.25)
    elif key == "COMPRESSED":
        headers["Content-Encoding"] = "gzip"
    body = {
        "BADJSON": b"private-backend-detail: not json",
        "HUGE": b"x" * 70000,
    }.get(key, json.dumps(payload).encode())
    return status, headers, body


@contextmanager
def deepcopy_upstream():
    """Serve the Deepcopy API /ibkr routes on a real loopback socket."""
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            calls.append((self.path, dict(self.headers)))
            if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                key, status, payload = "", 401, {"secret": "private-backend-detail"}
            else:
                key, status, payload = route(self.path)
            status, headers, body = misbehave(key, status, payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for name, value in headers.items():
                self.send_header(name, value)
            self.end_headers()
            try:
                self.write(body, drip=key == "DRIP")
            except (BrokenPipeError, ConnectionResetError):
                pass

        def write(self, body: bytes, drip: bool) -> None:
            if not drip:
                self.wfile.write(body)
                return
            for byte in body:
                self.wfile.write(bytes([byte]))
                self.wfile.flush()
                time.sleep(0.015)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    try:
        yield (
            {"base_url": f"http://127.0.0.1:{server.server_port}/v1", "token": TOKEN},
            calls,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch, tmp_path):
    import os

    for key in os.environ:
        if key.startswith(("MCP_", "FASTMCP_")):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def settings():
    return Settings(_env_file=None)


@pytest.fixture
def deepcopy_api():
    with deepcopy_upstream() as api:
        yield api


@pytest.fixture
def api_settings(deepcopy_api):
    return Settings(_env_file=None, deepcopy_api=deepcopy_api[0])
