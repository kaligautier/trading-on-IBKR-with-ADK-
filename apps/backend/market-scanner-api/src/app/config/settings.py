"""Validated configuration; secrets are excluded from representations/errors."""

import os
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore", hide_input_in_errors=True
    )

    DATABASE_URL: SecretStr
    DATABASE_SCHEMA: str = Field(
        default="market_scanner", pattern=r"^[a-z_][a-z0-9_]{0,62}$"
    )
    DATABASE_POOL_SIZE: int = Field(default=1, ge=1, le=2)
    DATABASE_POOL_TIMEOUT: float = Field(default=5, gt=0, le=30)
    AUTH_MODE: Literal["token", "cloud_run"] = "token"
    API_TOKEN: SecretStr = SecretStr("")

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError:
            raise ValueError("Use a PostgreSQL reader URL") from None
        if url.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}:
            raise ValueError("Use a PostgreSQL reader URL")
        if not url.host or not url.database or url.username != "market_scanner_reader":
            raise ValueError("Use the dedicated market_scanner_reader role")
        if any(key not in {"sslmode", "sslrootcert"} for key in url.query):
            raise ValueError("Unsupported database URL option")
        if any(not isinstance(value, str) for value in url.query.values()):
            raise ValueError("Repeated database URL options are unsupported")
        if url.query.get("sslmode") not in {None, "disable", "verify-full"}:
            raise ValueError("Use sslmode=verify-full, or disable for localhost")
        if (
            url.host not in {"localhost", "127.0.0.1", "::1"}
            and url.query.get("sslmode") != "verify-full"
        ):
            raise ValueError("Remote PostgreSQL requires sslmode=verify-full")
        return value

    @model_validator(mode="after")
    def validate_authentication(self) -> Self:
        if self.AUTH_MODE == "token" and len(self.API_TOKEN.get_secret_value()) < 16:
            raise ValueError("Configure an API_TOKEN of at least 16 characters")
        if self.AUTH_MODE == "cloud_run" and not os.getenv("K_SERVICE"):
            raise ValueError("cloud_run authentication requires a Cloud Run service")
        return self
