"""MomentumApiSettings environment configuration."""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings

from app.api.config import validate_api_url


class MomentumApiSettings(BaseSettings):
    MOMENTUM_API_URL: str = Field(
        default="http://localhost:8000",
        description="Momentum API base URL for analyses and ticker suggestions.",
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

    SUGGESTION_HASH_SECRET: SecretStr = Field(
        ...,
        repr=False,
        description=(
            "Shared HMAC key for caller pseudonymization and suggestion signing."
        ),
    )

    @field_validator("MOMENTUM_API_URL")
    @classmethod
    def validate_momentum_api_url(cls, value: str) -> str:
        return validate_api_url(value)

    @field_validator("SUGGESTION_HASH_SECRET")
    @classmethod
    def require_signing_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value():
            raise ValueError("SUGGESTION_HASH_SECRET is required")
        return value
