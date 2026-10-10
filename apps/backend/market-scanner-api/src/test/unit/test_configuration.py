import base64

import pytest
from pydantic import ValidationError

from app.config.settings import Settings
from app.models.cursor import Cursor, InvalidCursorError

BASE = "postgresql://market_scanner_reader:private-password@localhost/scanner"


@pytest.mark.parametrize(
    "url",
    [
        BASE.replace("market_scanner_reader", "admin"),
        BASE.replace("localhost", "remote.example"),
        BASE + "?sslmode=require",
        BASE + "?sslmode=verify-full&ssl=disable",
        BASE + "?sslmode=disable&sslmode=verify-full",
        "not-a-database-url",
    ],
)
def test_unsafe_database_configuration_is_rejected_without_exposing_secret(url):
    with pytest.raises(ValidationError) as error:
        Settings(DATABASE_URL=url, API_TOKEN="test-token-long-enough", _env_file=None)
    assert "private-password" not in str(error.value)


def test_authentication_cannot_be_disabled_outside_cloud_run(monkeypatch):
    monkeypatch.delenv("K_SERVICE", raising=False)
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL=BASE, AUTH_MODE="cloud_run", _env_file=None)
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL=BASE, API_TOKEN="", _env_file=None)
    with pytest.raises(ValidationError):
        Settings(
            DATABASE_URL=BASE,
            API_TOKEN="test-token-long-enough",
            DATABASE_SCHEMA='bad";--',
            _env_file=None,
        )


@pytest.mark.parametrize(
    "payload",
    [
        b'{"version":2,"created_at":"2026-10-05T00:00:00Z","id":"00000000-0000-0000-0000-000000000001"}',
        b'{"version":1,"created_at":"2026-10-05T00:00:00","id":"00000000-0000-0000-0000-000000000001"}',
        b"{}",
    ],
)
def test_cursor_rejects_unsupported_versions_and_naive_dates(payload):
    with pytest.raises(InvalidCursorError):
        Cursor.decode(base64.urlsafe_b64encode(payload).decode())
