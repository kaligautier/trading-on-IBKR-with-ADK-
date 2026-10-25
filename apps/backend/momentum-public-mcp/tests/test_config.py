"""Reject unsafe deployment configuration before opening network connections."""

import pytest
from pydantic import ValidationError

from momentum_public_mcp.config import Settings


def settings(**values):
    return Settings(_env_file=None, SUGGESTION_HASH_SECRET="test-signing-key", **values)


@pytest.mark.parametrize("port", [0, 65536])
def test_rejects_invalid_listening_port(port):
    with pytest.raises(ValidationError):
        settings(PORT=port)


@pytest.mark.parametrize("field", ["MOMENTUM_API_URL", "MARKET_SCANNER_API_URL"])
@pytest.mark.parametrize(
    "url", ["http://private.example", "https://user:password@api.example", "relative"]
)
def test_rejects_remote_cleartext_credentials_and_relative_urls(field, url):
    with pytest.raises(ValidationError):
        settings(**{field: url})


def test_validates_proxies_and_redacts_signing_key():
    configured = settings(
        MOMENTUM_API_URL="https://api.example/", TRUSTED_PROXIES="127.0.0.0/8"
    )
    assert configured.MOMENTUM_API_URL == "https://api.example"
    assert "test-signing-key" not in repr(configured)
    assert "test-signing-key" not in configured.model_dump_json()
    with pytest.raises(ValidationError):
        settings(TRUSTED_PROXIES="not-a-network")


def test_empty_signing_key_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, SUGGESTION_HASH_SECRET="")


@pytest.mark.parametrize(
    "values",
    [
        {"LOG_SUCCESS_SAMPLE_RATE": -0.1},
        {"LOG_SUCCESS_SAMPLE_RATE": 1.1},
        {"LOG_SUCCESS_SAMPLE_RATE": float("nan")},
        {"LOG_SLOW_REQUEST_MS": 0},
    ],
)
def test_rejects_invalid_sampling_configuration(values):
    with pytest.raises(ValidationError):
        settings(**values)
