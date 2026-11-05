"""Validated environment configuration, following the other Python backends."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import SettingsConfigDict

from app.api.market_scanner.config.settings import (
    MarketScannerApiSettings,
)
from app.api.momentum.config.settings import MomentumApiSettings
from app.config.constants import DEFAULT_LIST_PAGE_SIZE
from app.security import TrustedProxyNetworks


class Settings(MomentumApiSettings, MarketScannerApiSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore", hide_input_in_errors=True
    )

    TRUSTED_PROXIES: str = Field(
        default="",
        description=(
            "Comma-separated trusted proxy CIDRs; empty trusts only the direct peer."
        ),
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
            "Google Cloud project for log correlation and Cloud Trace export; "
            "empty disables export."
        ),
    )

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Application logging level."
    )

    K_SERVICE: str = Field(
        default="momentum-public-mcp", description="Service name supplied by Cloud Run."
    )

    DEFAULT_PAGE_SIZE: int = Field(
        default=DEFAULT_LIST_PAGE_SIZE,
        ge=1,
        le=100,
        description="Maximum components per MCP discovery page (not analysis results).",
    )

    @field_validator("TRUSTED_PROXIES")
    @classmethod
    def validate_proxies(cls, value: str) -> str:
        TrustedProxyNetworks.from_csv(value)
        return value
