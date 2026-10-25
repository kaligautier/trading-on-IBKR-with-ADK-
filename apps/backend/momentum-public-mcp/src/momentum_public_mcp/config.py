"""Validated environment configuration, following the other Python backends."""

from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from momentum_public_mcp.security import TrustedProxyNetworks


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore", hide_input_in_errors=True
    )

    MOMENTUM_API_URL: str = Field(
        default="http://localhost:8000",
        description="Momentum API base URL for analyses and ticker suggestions.",
    )
    MARKET_SCANNER_API_URL: str = Field(
        default="http://localhost:8003",
        description="Market Scanner consultation API base URL.",
    )
    SUGGESTION_HASH_SECRET: SecretStr = Field(
        ...,
        repr=False,
        description=(
            "Shared HMAC key for caller pseudonymization and suggestion signing."
        ),
    )
    TRUSTED_PROXIES: str = Field(
        default="",
        description=(
            "Comma-separated trusted proxy CIDRs; empty trusts only the direct peer."
        ),
    )
    MOMENTUM_API_USE_IAM: bool = Field(
        default=False,
        description="Authenticate private API calls with Cloud Run identity tokens.",
    )
    MOMENTUM_API_TOKEN: SecretStr = Field(
        default=SecretStr(""),
        repr=False,
        description="Momentum API bearer token, used only when IAM is disabled.",
    )
    MARKET_SCANNER_API_TOKEN: SecretStr = Field(
        default=SecretStr(""),
        repr=False,
        description="Scanner API bearer token, used only when IAM is disabled.",
    )
    PORT: int = Field(
        default=8080,
        ge=1,
        le=65535,
        description="HTTP listening port, supplied by Cloud Run in production.",
    )
    GOOGLE_CLOUD_PROJECT: str = Field(
        default="",
        description=(
            "Google Cloud project used to correlate structured logs with traces."
        ),
    )

    LOG_SUCCESS_SAMPLE_RATE: float = Field(
        default=1.0,
        ge=0,
        le=1,
        description="Fraction of successful fast requests retained after completion.",
    )
    LOG_SLOW_REQUEST_MS: int = Field(
        default=2000,
        ge=1,
        description="Always retain requests slower than this duration in milliseconds.",
    )
    K_SERVICE: str = Field(
        default="momentum-public-mcp", description="Service name supplied by Cloud Run."
    )
    K_REVISION: str = Field(
        default="local", description="Deployment revision supplied by Cloud Run."
    )

    @field_validator("MOMENTUM_API_URL", "MARKET_SCANNER_API_URL")
    @classmethod
    def validate_api_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("API URL must be an absolute HTTP URL")
        if parsed.username or parsed.password:
            raise ValueError("API URL must not contain credentials")
        local_hosts = {
            "localhost",
            "127.0.0.1",
            "::1",
            "momentum-api",
            "market-scanner-api",
        }
        if parsed.scheme != "https" and parsed.hostname not in local_hosts:
            raise ValueError("API URL must use HTTPS outside local development")
        return value.rstrip("/")

    @field_validator("SUGGESTION_HASH_SECRET")
    @classmethod
    def require_signing_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError("SUGGESTION_HASH_SECRET is required")
        return value

    @field_validator("TRUSTED_PROXIES")
    @classmethod
    def validate_proxies(cls, value: str) -> str:
        TrustedProxyNetworks.from_csv(value)
        return value
