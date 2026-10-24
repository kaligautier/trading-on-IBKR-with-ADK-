"""Intake HTTP authorization and representation checks must precede writes."""

import hashlib
import hmac
from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from app.app_factory import create_app
from app.config.settings import Settings
from app.domain.suggestions import Suggestion, SuggestionInput

SECRET = "disposable-suggestion-key"
CALLER = "a" * 64
HEADERS = {
    "Authorization": "Bearer disposable-reader-token",
    "X-Momentum-Caller": CALLER,
    "X-Momentum-Signature": hmac.new(
        SECRET.encode(), CALLER.encode(), hashlib.sha256
    ).hexdigest(),
}


class Store:
    def __init__(self):
        self.calls = []

    async def submit(self, symbol, reason, caller):
        value = SuggestionInput(symbol, reason, caller)
        self.calls.append(value)
        return Suggestion(
            UUID(int=1),
            value.symbol,
            value.reason,
            "pending",
            "mcp",
            datetime.now(UTC),
            None,
            None,
        )


@pytest.fixture
async def client():
    app = create_app(
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql://momentum_results_reader:local@localhost/momentum",
            AUTH_MODE="token",
            API_TOKEN="disposable-reader-token",
            SUGGESTION_HASH_SECRET=SECRET,
        )
    )
    store = Store()
    app.state.suggestions = store
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        yield client, store


async def test_original_intake_contract(client):
    connection, store = client
    response = await connection.post(
        "/suggestions", json={"symbol": " msft ", "reason": " test "}, headers=HEADERS
    )
    assert response.status_code == 202, response.text
    assert response.json()["symbol"] == "MSFT"
    assert response.json()["status"] == "pending"
    assert len(store.calls) == 1
    assert "suggested_by" not in response.json()
    assert response.headers["cache-control"] == "no-store"
    assert "etag" not in response.headers


@pytest.mark.parametrize(
    "headers,status",
    [
        ({"X-Momentum-Signature": "0" * 64}, 403),
        ({"X-Momentum-Caller": "not-a-hash"}, 403),
        ({"Accept": "text/html"}, 406),
        ({"Accept-Encoding": "identity;q=0"}, 406),
        ({"If-Match": '"old"'}, 400),
        ({"Content-Type": "text/plain"}, 415),
    ],
)
async def test_rejections_do_not_write(client, headers, status):
    connection, store = client
    response = await connection.post(
        "/suggestions", json={"symbol": "MSFT"}, headers={**HEADERS, **headers}
    )
    assert response.status_code == status
    assert not store.calls


async def test_body_limit_and_unknown_fields(client):
    connection, store = client
    response = await connection.post(
        "/suggestions",
        content=b" " * 4097,
        headers={**HEADERS, "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    response = await connection.post(
        "/suggestions", json={"symbol": "MSFT", "status": "approved"}, headers=HEADERS
    )
    assert response.status_code == 400
    assert not store.calls


async def test_intake_method_allowlist(client):
    connection, store = client
    response = await connection.options("/suggestions", headers=HEADERS)
    assert response.status_code == 204
    assert response.headers["allow"] == "POST, OPTIONS"
    response = await connection.get("/suggestions", headers=HEADERS)
    assert response.status_code == 405
    assert response.headers["allow"] == "POST, OPTIONS"
    assert not store.calls
