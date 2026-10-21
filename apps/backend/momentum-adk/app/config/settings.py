"""Required gateway credentials, with no direct-provider fallback."""

from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    LITELLM_API_BASE: str
    LITELLM_API_KEY: SecretStr = Field(repr=False)
    MOMENTUM_QUICK_MODEL: str = "gemini-3.8-flash"
    MOMENTUM_DEEP_MODEL: str = "gemini-3.8-flash"

    @model_validator(mode="after")
    def validate_gateway(self):
        url = urlsplit(self.LITELLM_API_BASE)
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
        ):
            raise ValueError("Gateway must be a root HTTP URL")
        if url.scheme == "http" and url.hostname not in {"127.0.0.1", "::1"}:
            raise ValueError("Gateway requires HTTPS outside loopback")
        if not self.LITELLM_API_KEY.get_secret_value().strip():
            raise ValueError("Gateway virtual key is required")
        return self
