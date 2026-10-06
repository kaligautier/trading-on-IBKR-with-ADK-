"""
Tests for configuration module.

Tests:
- Settings loading
- Environment variable handling
- Configuration validation
"""

import pytest
from pydantic import ValidationError


@pytest.mark.parametrize("scanner_override", [None, "postgresql://scanner-override/db"])
def should_use_shared_database_url_with_explicit_override_priority(
    monkeypatch, scanner_override
):
    from app.config.settings import Settings

    shared_url = "postgresql://shared-aiven/db?sslmode=require"
    monkeypatch.delenv("MARKET_SCANNER_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", shared_url)
    monkeypatch.delenv("TA_DATABASE_URL", raising=False)
    if scanner_override is not None:
        monkeypatch.setenv("TA_DATABASE_URL", scanner_override)

    settings = Settings(_env_file=None, GOOGLE_CLOUD_PROJECT="test-project")

    assert settings.DATABASE_URL == (scanner_override or shared_url)


def test_settings_loads_successfully():
    """Test that settings load with required environment variables."""
    from app.config.settings import settings

    # Test that required settings are present and non-empty
    assert settings.GOOGLE_CLOUD_PROJECT is not None
    assert len(settings.GOOGLE_CLOUD_PROJECT) > 0
    assert settings.GOOGLE_CLOUD_LOCATION is not None
    assert len(settings.GOOGLE_CLOUD_LOCATION) > 0
    assert settings.GOOGLE_GENAI_USE_VERTEXAI is True


def test_settings_has_defaults():
    """Test that settings have appropriate default values."""
    import os
    from unittest.mock import patch

    from app.config.settings import Settings

    with patch.dict(os.environ, {}, clear=True):
        settings = Settings(
            GOOGLE_GENAI_USE_VERTEXAI=True,
            GOOGLE_CLOUD_PROJECT="test-project",
            GOOGLE_CLOUD_LOCATION="global",
        )

    assert settings.APP_NAME == "Market Scanner ADK"
    assert settings.PROJECT_NAME == "market-scanner-adk"
    assert settings.MODEL == "gemini-3.8-flash"
    assert settings.HOST == "0.0.0.0"
    assert settings.PORT == 8000


def test_agent_dir_property():
    """Test that AGENT_DIR property returns correct path."""
    from pathlib import Path

    from app.config.settings import settings

    agent_dir = settings.AGENT_DIR

    assert isinstance(agent_dir, str)
    assert agent_dir.endswith("components/agents")
    assert Path(agent_dir).name == "agents"


def test_settings_validation():
    """Test that settings validate required fields."""
    import os
    from unittest.mock import patch

    # Remove required env var temporarily
    with patch.dict(os.environ, {}, clear=True):
        # Should raise ValidationError for missing required fields
        with pytest.raises(ValidationError):
            from app.config.settings import Settings

            Settings(_env_file=None)
