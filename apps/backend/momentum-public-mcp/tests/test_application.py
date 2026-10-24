"""Cloud Run runtime configuration tests."""

from momentum_public_mcp.application import (
    MomentumPublicSettings,
)


def test_cloud_run_identity_is_enabled_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("MOMENTUM_API_URL", "https://momentum.test")
    monkeypatch.setenv("MARKET_SCANNER_API_URL", "https://scanner.test")
    monkeypatch.setenv("SUGGESTION_HASH_SECRET", "test-secret")
    monkeypatch.setenv("MOMENTUM_API_USE_IAM", "true")

    settings = MomentumPublicSettings.from_environment()

    assert settings.use_cloud_run_identity is True
