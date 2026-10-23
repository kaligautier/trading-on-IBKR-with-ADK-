"""End-to-end application protocol, before introducing any database dependency."""

import logging

import httpx
import pytest

from app.application import create_app
from app.config import Settings
from app.http.problems import APIError

BEARER = "Bearer disposable-reader-token"


@pytest.fixture
async def client():
    app = create_app(
        Settings(
            DATABASE_URL="postgresql://momentum_results_reader:local@localhost/momentum",
            API_TOKEN="disposable-reader-token",
        )
    )

    @app.get("/failure")
    async def failure():
        raise APIError(503, "store-unavailable")

    @app.get("/crash")
    async def crash():
        raise RuntimeError("never expose credentials or SQL")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test",
    ) as connection:
        yield connection


async def test_liveness_and_authenticated_openapi(client):
    assert (await client.get("/health")).json() == {"status": "ok"}
    missing = await client.get("/openapi.json")
    assert missing.status_code == 401 and missing.content == b""
    assert missing.headers["www-authenticate"] == 'Bearer realm="momentum-api"'
    schema = await client.get("/openapi.json", headers={"Authorization": BEARER})
    assert schema.status_code == 200 and "openapi" in schema.json()


@pytest.mark.parametrize(
    ("headers", "query", "status", "challenge"),
    [
        ({"Authorization": "Bearer wrong"}, "", 401, "invalid_token"),
        ({"Authorization": "Basic abc"}, "", 401, None),
        ({"Authorization": "Bearer bad space"}, "", 400, "invalid_request"),
        ({"Authorization": BEARER}, "?access_token=secret", 400, "invalid_request"),
        (
            [("Authorization", BEARER), ("Authorization", BEARER)],
            "",
            400,
            "invalid_request",
        ),
    ],
)
async def test_credentials(client, headers, query, status, challenge):
    response = await client.get("/openapi.json" + query, headers=headers)
    assert response.status_code == status
    if challenge:
        assert f'error="{challenge}"' in response.headers["www-authenticate"]
    else:
        assert response.content == b""


async def test_head_options_methods_and_no_request_body(client):
    get = await client.get("/health")
    head = await client.head("/health")
    assert head.status_code == 200 and not head.content
    assert head.headers["etag"] == get.headers["etag"]
    assert int(head.headers["content-length"]) == len(get.content)
    options = await client.options("/health")
    assert options.status_code == 204 and not options.content
    assert options.headers["allow"] == "GET, HEAD, OPTIONS"
    assert "content-length" not in options.headers
    post = await client.post("/health")
    assert post.status_code == 405 and post.headers["allow"] == options.headers["allow"]
    assert (await client.request("UNREGISTERED", "/health")).status_code == 501
    body = await client.request("GET", "/health", content=b"{}")
    assert body.status_code == 400


async def test_conditions_and_negotiation(client):
    get = await client.get("/health")
    tag = get.headers["etag"]
    cached = await client.get("/health", headers={"If-None-Match": "W/" + tag})
    assert cached.status_code == 304 and not cached.content
    assert cached.headers["etag"] == tag
    assert "content-length" not in cached.headers
    assert cached.headers["cache-control"] == "no-store"
    assert (
        await client.get("/health", headers={"If-Match": '"bad"'})
    ).status_code == 412
    assert (
        await client.get("/health", headers={"Accept": "text/html"})
    ).status_code == 406
    assert (
        await client.get("/health", headers={"Accept-Encoding": "identity;q=0"})
    ).status_code == 406
    assert (
        await client.get(
            "/health", headers={"If-Modified-Since": "tomorrow", "Range": "bytes=0-1"}
        )
    ).status_code == 200


async def test_errors_are_safe_bodyless_when_needed_and_never_logged(client, caplog):
    caplog.set_level(logging.INFO, logger="momentum_api")
    auth = {"Authorization": BEARER}
    missing = await client.get("/absent?private=hidden", headers=auth)
    assert missing.status_code == 404
    assert missing.headers["content-type"] == "application/problem+json"
    assert missing.json()["status"] == 404
    assert (await client.head("/absent", headers=auth)).content == b""
    failure = await client.get("/failure", headers=auth)
    assert failure.status_code == 503
    empty = await client.get("/failure", headers={**auth, "Accept": "application/json"})
    assert empty.status_code == 503 and not empty.content
    crash = await client.get("/crash", headers=auth)
    assert crash.status_code == 500 and "SQL" not in crash.text
    assert "disposable-reader-token" not in caplog.text
    assert "hidden" not in caplog.text and "/absent" not in caplog.text
    assert "status=500" in caplog.text


async def test_error_format_and_repeated_accept_fields(client):
    auth = {"Authorization": BEARER, "Accept": "application/problem+json"}
    error = await client.get("/failure", headers=auth)
    assert error.status_code == 503 and error.json()["code"] == "store-unavailable"
    response = await client.get(
        "/health", headers=[("Accept", "text/html"), ("Accept", "application/json")]
    )
    assert response.status_code == 200
