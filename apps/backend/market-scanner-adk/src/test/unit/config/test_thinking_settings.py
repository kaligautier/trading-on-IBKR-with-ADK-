"""Validate the Gemini 3.8 Flash model, EU location and agent thinking levels."""

import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def should_default_to_gemini_38_with_medium_research_and_low_synthesis(monkeypatch):
    for key in (
        "MODEL",
        "MARKET_SCANNER_MODEL",
        "GOOGLE_CLOUD_LOCATION",
        "MARKET_SCANNER_GOOGLE_CLOUD_LOCATION",
        "RESEARCHER_THINKING_LEVEL",
        "MARKET_SCANNER_RESEARCHER_THINKING_LEVEL",
        "SYNTHESIZER_THINKING_LEVEL",
        "MARKET_SCANNER_SYNTHESIZER_THINKING_LEVEL",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(
        _env_file=None,
        GOOGLE_CLOUD_PROJECT="test-project",
    )

    assert settings.MODEL == "gemini-3.8-flash"
    assert settings.GOOGLE_CLOUD_LOCATION == "eu"
    assert settings.RESEARCHER_THINKING_LEVEL == "MEDIUM"
    assert settings.SYNTHESIZER_THINKING_LEVEL == "LOW"


def should_prefer_scanner_overrides_to_shared_agent_settings(monkeypatch):
    monkeypatch.setenv("MODEL", "gemini-3.1-pro-preview")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "europe-west1")
    monkeypatch.setenv("MARKET_SCANNER_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("MARKET_SCANNER_GOOGLE_CLOUD_LOCATION", "eu")
    monkeypatch.setenv("SYNTHESIZER_THINKING_LEVEL", "MEDIUM")
    monkeypatch.setenv("MARKET_SCANNER_SYNTHESIZER_THINKING_LEVEL", "HIGH")

    settings = Settings(_env_file=None, GOOGLE_CLOUD_PROJECT="test-project")

    assert settings.MODEL == "gemini-3.8-flash"
    assert settings.GOOGLE_CLOUD_LOCATION == "eu"
    assert settings.SYNTHESIZER_THINKING_LEVEL == "HIGH"


@pytest.mark.parametrize("level", ["LOW", "MEDIUM", "HIGH"])
def should_load_the_synthesis_level_from_the_environment(monkeypatch, level):
    monkeypatch.delenv("MARKET_SCANNER_SYNTHESIZER_THINKING_LEVEL", raising=False)
    monkeypatch.setenv("SYNTHESIZER_THINKING_LEVEL", level)

    settings = Settings(
        _env_file=None,
        GOOGLE_CLOUD_PROJECT="test-project",
        GOOGLE_CLOUD_LOCATION="global",
    )

    assert settings.SYNTHESIZER_THINKING_LEVEL == level


@pytest.mark.parametrize("level", ["MINIMAL", "8192", "HIGHT"])
def should_reject_an_unsupported_thinking_level(monkeypatch, level):
    monkeypatch.delenv("MARKET_SCANNER_SYNTHESIZER_THINKING_LEVEL", raising=False)
    monkeypatch.setenv("SYNTHESIZER_THINKING_LEVEL", level)

    with pytest.raises(ValidationError, match="SYNTHESIZER_THINKING_LEVEL"):
        Settings(
            _env_file=None,
            GOOGLE_CLOUD_PROJECT="test-project",
            GOOGLE_CLOUD_LOCATION="global",
        )
