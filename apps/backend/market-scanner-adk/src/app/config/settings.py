"""Application configuration using Pydantic BaseSettings."""

import os
from pathlib import Path
from typing import Literal

from dotenv import find_dotenv, load_dotenv
from pydantic import AliasChoices, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.utils.error import ConfigurationError


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    Configuration is loaded from:
    1. Environment variables
    2. .env file (in non-Docker environments)
    3. Default values defined below

    All settings are type-safe and validated by Pydantic.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )

    # Auto-load .env file in non-Docker environments
    if not os.getenv("DOCKER_ENV"):
        load_dotenv(find_dotenv(".env"))

    # Application metadata
    APP_NAME: str = Field(
        default="Market Scanner ADK",
        description="Application name displayed in API documentation",
    )
    APP_DESCRIPTION: str = Field(
        default="Independent daily market scanner",
        description="Application description for API documentation",
    )
    APP_VERSION: str = Field(
        default="0.1.0",
        description="Application version",
    )
    PROJECT_NAME: str = Field(
        default="market-scanner-adk",
        description="Project identifier used in paths and naming",
    )

    # Server configuration
    HOST: str = Field(
        default="0.0.0.0",
        description="Server host address (0.0.0.0 for all interfaces)",
    )
    PORT: int = Field(
        default=8000,
        description="Server port",
    )
    DEBUG: bool = Field(
        default=False,
        description="Enable debug mode (disable in production)",
    )

    # Logging configuration
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    # Agent configuration
    AGENT_NAME: str = Field(
        default="market_scanner",
        description="Primary agent name",
    )
    MODEL: str = Field(
        default="gemini-3.8-flash",
        validation_alias=AliasChoices("MARKET_SCANNER_MODEL", "MODEL"),
        description="AI model to use for the agent",
    )

    RESEARCHER_THINKING_LEVEL: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        default="MEDIUM",
        validation_alias=AliasChoices(
            "MARKET_SCANNER_RESEARCHER_THINKING_LEVEL", "RESEARCHER_THINKING_LEVEL"
        ),
        description="Gemini 3.8 Flash research reasoning effort.",
    )

    SYNTHESIZER_THINKING_LEVEL: Literal["LOW", "MEDIUM", "HIGH"] = Field(
        default="LOW",
        validation_alias=AliasChoices(
            "MARKET_SCANNER_SYNTHESIZER_THINKING_LEVEL", "SYNTHESIZER_THINKING_LEVEL"
        ),
        description="Gemini 3.8 Flash synthesis reasoning effort.",
    )

    MARKET_SCANNER_ASSET_KEYS: tuple[str, ...] | None = Field(
        default=None, description="Optional subset of catalog keys to collect."
    )

    # Agent directory (computed from project structure)
    @property
    def AGENT_DIR(self) -> str:  # noqa: N802
        """Get the absolute path to the agents directory."""
        return str(Path(__file__).parent.parent / "components" / "agents")

    # Instructions directory (computed from project structure)
    @property
    def INSTRUCTIONS_DIR(self) -> str:  # noqa: N802
        """Get the absolute path to the instructions templates directory."""
        return str(Path(__file__).parent.parent / "instructions" / "templates")

    # Google Cloud Platform configuration (required for Vertex AI)
    GOOGLE_APPLICATION_CREDENTIALS: str | None = Field(
        default=None,
        description="Optional path to local Application Default Credentials.",
    )
    GOOGLE_GENAI_USE_VERTEXAI: bool = Field(
        default=True,
        description="Enable Vertex AI for Google Generative AI (required)",
    )
    GOOGLE_CLOUD_PROJECT: str = Field(
        description="GCP project ID (required)",
    )
    GOOGLE_CLOUD_LOCATION: str = Field(
        default="eu",
        validation_alias=AliasChoices(
            "MARKET_SCANNER_GOOGLE_CLOUD_LOCATION", "GOOGLE_CLOUD_LOCATION"
        ),
        description="Vertex AI inference location, separate from the Cloud Run region.",
    )

    # Session management
    USER_ID: str = Field(
        default="api_user",
        description="Default user ID for session management",
    )
    ADK_ALLOW_ORIGINS: list[str] = Field(
        default_factory=list,
        description="Explicit browser origins allowed by the ADK server.",
    )

    DATABASE_URL: str = Field(
        default="",
        repr=False,
        validation_alias=AliasChoices(
            "MARKET_SCANNER_DATABASE_URL", "TA_DATABASE_URL", "DATABASE_URL"
        ),
    )
    DATABASE_SCHEMA: str = Field(
        default="market_scanner", pattern=r"^[a-z_][a-z0-9_]{0,62}$"
    )
    DATABASE_POOL_SIZE: int = Field(default=1, ge=1, le=10)
    DATABASE_POOL_TIMEOUT: float = Field(default=30, gt=0)
    MARKET_SCANNER_APP_NAME: str = "market_scanner"
    MARKET_SCANNER_TOKEN: str = ""


# Singleton settings instance with error handling
try:
    settings = Settings()
except ValidationError as e:
    raise ConfigurationError(
        message="Configuration validation failed",
        details={"pydantic_errors": e.errors(include_input=False)},
    ) from e
