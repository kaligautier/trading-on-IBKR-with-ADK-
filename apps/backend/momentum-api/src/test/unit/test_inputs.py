from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import SecretStr, ValidationError

from app.config import Settings
from app.query import Cursor, Query

URL = "postgresql://momentum_results_reader:fixture-only@localhost:55451/momentum"
TOKEN = "disposable-token-for-tests"


def settings(**overrides):
    return Settings(
        _env_file=None, **{"DATABASE_URL": URL, "API_TOKEN": TOKEN, **overrides}
    )


def test_canonical_query_and_bound_cursor():
    query = Query.from_parameters("latest", " aapl ", "sell, BUY,Buy", 20, "")
    assert query.ticker == "AAPL"
    assert query.ratings == ("Buy", "Sell")
    cursor = Cursor(
        created_at=datetime(2026, 10, 22, tzinfo=UTC), id=UUID(int=1), scope=query.scope
    )
    token = cursor.encode()
    assert len(token) <= 512
    assert (
        Query.from_parameters("latest", "AAPL", "Buy,Sell", 100, token).cursor == cursor
    )
    for view, ticker, ratings in [
        ("history", "AAPL", "Buy,Sell"),
        ("latest", "MSFT", "Buy,Sell"),
        ("latest", "AAPL", None),
    ]:
        with pytest.raises(ValueError):
            Query.from_parameters(view, ticker, ratings, 20, token)


@pytest.mark.parametrize("ticker", ["", "../AAPL", "A" * 33, "AAPL;DROP", "a b", "é"])
def test_invalid_ticker(ticker):
    with pytest.raises(ValueError):
        Query.from_parameters("history", ticker, None, 20, "")


@pytest.mark.parametrize("ticker", ["^GSPC", "BRK.B", "EURUSD=X", "BTC-USD"])
def test_writer_ticker_vocabulary(ticker):
    assert Query.from_parameters("history", ticker, None, 20, "").ticker == ticker


@pytest.mark.parametrize("rating", ["", ",", "Buy,", "Buy,unknown", "Strong Buy"])
def test_invalid_rating(rating):
    with pytest.raises(ValueError):
        Query.from_parameters("latest", None, rating, 20, "")


@pytest.mark.parametrize("size", [0, -1, 101])
def test_page_bounds(size):
    with pytest.raises(ValueError):
        Query.from_parameters("history", None, None, size, "")


def test_view_defaults():
    assert Query.from_parameters("history", None, None, 20, "").ratings is None
    assert Query.from_parameters("recommendations", None, None, 10, "").ratings == (
        "Buy",
        "Overweight",
    )
    assert Query.from_parameters("latest", None, None, 20, "").cursor is None


@pytest.mark.parametrize("token", ["bad", "a" * 513, "e30=", "====", "💰"])
def test_invalid_cursor(token):
    with pytest.raises(ValueError):
        Query.from_parameters("history", None, None, 20, token)


def test_cursor_rejects_naive_dates_and_unknown_versions():
    for changes in [
        {"created_at": "2026-10-22T00:00:00"},
        {"version": 2},
        {"surprise": True},
    ]:
        with pytest.raises(ValidationError):
            Cursor.model_validate(
                {
                    "created_at": "2026-10-22T00:00:00Z",
                    "id": str(UUID(int=1)),
                    "scope": "a" * 64,
                    **changes,
                }
            )


def test_secure_configuration_and_redaction():
    config = settings()
    assert config.DATABASE_POOL_SIZE == 1
    assert isinstance(config.DATABASE_URL, SecretStr)
    assert "fixture-only" not in repr(config)
    assert TOKEN not in repr(config)


@pytest.mark.parametrize(
    "url",
    [
        "invalid",
        "sqlite:///momentum",
        URL.replace("momentum_results_reader", "postgres"),
        URL.replace("/momentum", "/other"),
        URL.replace("localhost", "remote.invalid"),
        URL + "?sslmode=require",
        URL + "?options=admin",
        URL + "?sslmode=disable&sslmode=disable",
        URL.replace(":fixture-only", ""),
    ],
)
def test_reject_unsafe_database_configuration(url):
    with pytest.raises(ValidationError) as result:
        settings(DATABASE_URL=url)
    assert "fixture-only" not in str(result.value)


def test_verified_remote_database():
    config = settings(
        DATABASE_URL=URL.replace("localhost", "remote.invalid")
        + "?sslmode=verify-full&sslrootcert=/etc/database/ca.pem"
    )
    assert config.DATABASE_POOL_SIZE == 1


@pytest.mark.parametrize("token", ["short", "x" * 16 + "\n", "é" * 20])
def test_invalid_bearer_token(token):
    with pytest.raises(ValidationError):
        settings(API_TOKEN=token)


def test_cloud_auth_cannot_run_unprotected_locally(monkeypatch):
    monkeypatch.delenv("K_SERVICE", raising=False)
    with pytest.raises(ValidationError):
        settings(AUTH_MODE="cloud_run", API_TOKEN="")
    monkeypatch.setenv("K_SERVICE", "momentum-api")
    assert settings(AUTH_MODE="cloud_run", API_TOKEN="").AUTH_MODE == "cloud_run"
