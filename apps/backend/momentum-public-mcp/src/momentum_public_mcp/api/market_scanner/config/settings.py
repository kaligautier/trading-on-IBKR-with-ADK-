"""MarketScannerApiSettings environment configuration."""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings

from momentum_public_mcp.api.config import validate_api_url


class MarketScannerApiSettings(BaseSettings):
    MARKET_SCANNER_API_URL: str = Field(
        default="http://localhost:8003",
        description="Market Scanner consultation API base URL.",
    )

    MARKET_SCANNER_API_TOKEN: SecretStr = Field(
        default=SecretStr(""),
        repr=False,
        description="Scanner API bearer token, used only when IAM is disabled.",
    )

    @field_validator("MARKET_SCANNER_API_URL")
    @classmethod
    def validate_market_scanner_api_url(cls, value: str) -> str:
        return validate_api_url(value)
