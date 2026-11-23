import pytest
from pydantic import ValidationError

from app.auth import ExpiringJWTVerifier, create_auth
from app.config.settings import Settings

JWT = {
    "transport": "http",
    "auth_mode": "jwt",
    "jwt_jwks_uri": "https://identity.example.com/jwks",
    "jwt_issuer": "https://identity.example.com/",
    "jwt_audience": "deepcopy-mcp",
}


@pytest.mark.parametrize(
    "values",
    [
        {"port": 0},
        {"page_size": 0},
        {"log_max_payload_length": 0},
        {"log_max_payload_length": 100001},
        {"auth_mode": "jwt"},
        {"environment": "production"},
        {"allowed_hosts": ["*"]},
        {"allowed_hosts": []},
        {"allowed_origins": ["*"]},
        {**JWT, "jwt_jwks_uri": "http://identity.example.com/jwks"},
        {**JWT, "transport": "stdio"},
        {**JWT, "required_scopes": []},
    ],
)
def test_rejects_invalid_configuration(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_environment_override(monkeypatch):
    monkeypatch.setenv("MCP_PORT", "9000")
    assert Settings(_env_file=None).port == 9000


def test_auth_factory(settings):
    assert create_auth(settings) is None
    verifier = create_auth(Settings(_env_file=None, environment="production", **JWT))
    assert isinstance(verifier, ExpiringJWTVerifier)
    assert verifier.required_scopes == ["mcp:access"]


def test_settings_are_not_shared(settings):
    settings.required_scopes.append("extra")
    assert Settings(_env_file=None).required_scopes == ["mcp:access"]


def test_logging_environment_override(monkeypatch):
    monkeypatch.setenv("MCP_LOG_TOOL_ARGUMENTS", "false")
    monkeypatch.setenv("MCP_LOG_MAX_PAYLOAD_LENGTH", "250")
    settings = Settings(_env_file=None)
    assert settings.log_tool_arguments is False
    assert settings.log_max_payload_length == 250
