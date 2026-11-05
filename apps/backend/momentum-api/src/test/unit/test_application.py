"""End-to-end application protocol, before introducing any database dependency."""

import json
import logging
from unittest.mock import AsyncMock

import httpx
import pytest

from app.app_factory import create_app
from app.config.settings import Settings
from app.domain.analyses.models import AnalysisPage
from app.presentation.http.problems import APIError
from app.services.analysis_service import AnalysisService

BEARER = "Bearer disposable-reader-token"


@pytest.fixture
def reader():
    return AsyncMock(spec=AnalysisService)


@pytest.fixture
async def client(reader):
    app = create_app(
        Settings(
            _env_file=None,
            AUTH_MODE="token",
            DATABASE_POOL_SIZE=1,
            DATABASE_POOL_TIMEOUT=5,
            DATABASE_URL="postgresql://momentum_results_reader:local@localhost/momentum",
            API_TOKEN="disposable-reader-token",
        )
    )
    app.state.service = reader

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


async def test_unexpected_failure_has_safe_correlated_diagnostics(client, caplog):
    with caplog.at_level(logging.ERROR, logger="momentum_api"):
        response = await client.get("/crash", headers={"Authorization": BEARER})
    assert response.status_code == 500
    assert response.headers["request-id"] in caplog.text
    diagnostic = json.loads(caplog.records[-1].getMessage())
    assert diagnostic["exception_type"] == "RuntimeError"
    assert diagnostic["source"].startswith("app.")
    assert "never expose credentials or SQL" not in caplog.text


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
    assert any(
        json.loads(record.getMessage()).get("status") == 500
        for record in caplog.records
        if record.name == "momentum_api"
    )
    unknown_method = await client.request("UNKNOWN", "/absent", headers=auth)
    assert unknown_method.status_code == 501


async def test_error_format_and_repeated_accept_fields(client):
    auth = {"Authorization": BEARER, "Accept": "application/problem+json"}
    error = await client.get("/failure", headers=auth)
    assert error.status_code == 503 and error.json()["code"] == "STORE_UNAVAILABLE"
    response = await client.get(
        "/health", headers=[("Accept", "text/html"), ("Accept", "application/json")]
    )
    assert response.status_code == 200


async def test_bearer_multiple_spaces_and_correlated_safe_failure(client, caplog):
    caplog.set_level(logging.INFO, logger="momentum_api")
    response = await client.get(
        "/openapi.json", headers={"Authorization": "bEaReR   disposable-reader-token"}
    )
    assert response.status_code == 200
    failure = await client.get("/crash", headers={"Authorization": BEARER})
    assert failure.json()["code"] == "INTERNAL_ERROR"
    assert failure.headers["request-id"] in caplog.text
    assert json.loads(caplog.records[-1].getMessage())["category"] == "INTERNAL_ERROR"


@pytest.mark.parametrize(
    "path, headers",
    [
        ("/openapi.json", {"Authorization": "Bearer\tdisposable-reader-token"}),
        ("/openapi.json?access_token=", {"Authorization": BEARER}),
    ],
)
async def test_malformed_bearer_transport(client, path, headers):
    response = await client.get(path, headers=headers)
    assert response.status_code == 400
    assert "invalid_request" in response.headers["www-authenticate"]


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize(
    ("accept", "status"),
    [
        ("application/json;charset=utf-8", 200),
        ('APPLICATION/JSON;CHARSET="UTF-8"', 200),
        ("application/json;charset=utf-8;q=0, */*;q=1", 406),
        ("application/json;charset=utf-8;profile=unknown", 406),
    ],
)
async def test_json_charset_negotiation(client, method, accept, status):
    response = await client.request(method, "/health", headers={"Accept": accept})
    assert response.status_code == status
    if method == "HEAD":
        assert response.content == b""
    elif status == 200:
        assert response.headers["content-type"] == "application/json"
        assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize(
    "path",
    [
        "/v1/analyses",
        "/v1/analyses/latest",
        "/v1/recommendations",
        "/v1/analyses/00000000-0000-0000-0000-000000000001",
        "/health",
        "/ready",
        "/openapi.json",
    ],
)
@pytest.mark.parametrize("query", ["unexpected=1", "unexpected=1&unexpected=2"])
async def test_all_read_routes_reject_unknown_queries(
    client, reader, method, path, query
):
    response = await client.request(
        method,
        path + "?" + query,
        headers={"Authorization": BEARER, "If-Match": '"different"'},
    )
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    if method == "HEAD":
        assert response.content == b""
    else:
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["code"] == "INVALID_ARGUMENT"
    reader.list.assert_not_awaited()
    reader.get.assert_not_awaited()
    reader.ready.assert_not_awaited()


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize(
    "path",
    [
        "/v1/analyses?ticker=AAPL&%74icker=MSFT",
        "/v1/analyses/latest?rating=Buy&rating=Sell",
        "/v1/recommendations?page_size=10&page_size=20",
        "/v1/analyses?page_token=&page_token=",
        "/v1/analyses?rating=Buy",
    ],
)
async def test_list_queries_still_reject_duplicates_and_unsupported_filters(
    client, reader, method, path
):
    response = await client.request(method, path, headers={"Authorization": BEARER})
    assert response.status_code == 400
    reader.list.assert_not_awaited()


async def test_query_validation_preserves_authentication_and_method_precedence(client):
    path = "/openapi.json?unexpected=1"
    assert (await client.get(path)).status_code == 401
    auth = {"Authorization": BEARER}
    assert (await client.get("/absent?unexpected=1", headers=auth)).status_code == 404
    assert (await client.post(path, headers=auth)).status_code == 405
    assert (await client.options(path, headers=auth)).status_code == 204
    token = await client.get("/openapi.json?access_token=bad", headers=auth)
    assert token.status_code == 400
    assert 'error="invalid_request"' in token.headers["www-authenticate"]


@pytest.mark.parametrize("method", ["GET", "HEAD"])
@pytest.mark.parametrize(
    ("path", "view", "extra", "ratings"),
    [
        ("/v1/analyses", "history", "", None),
        ("/v1/analyses/latest", "latest", "&rating=buy,sell", ("Buy", "Sell")),
        ("/v1/recommendations", "recommendations", "&rating=hold", ("Hold",)),
    ],
)
async def test_declared_list_parameters_reach_the_reader(
    client, reader, method, path, view, extra, ratings
):
    reader.list.return_value = AnalysisPage(items=[], next_page_token="")
    response = await client.request(
        method,
        path + "?ticker=aapl&page_size=1&page_token=" + extra,
        headers={"Authorization": BEARER},
    )
    assert response.status_code == 200
    reader.list.assert_awaited_once()
    query = reader.list.await_args.args[0]
    assert (query.view, query.ticker, query.page_size, query.cursor, query.ratings) == (
        view,
        "AAPL",
        1,
        None,
        ratings,
    )
