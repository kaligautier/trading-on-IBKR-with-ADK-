"""Cloud Run runtime configuration tests."""

from momentum_public_mcp.config import Settings


def test_cloud_run_identity_is_enabled_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("MOMENTUM_API_URL", "https://momentum.test")
    monkeypatch.setenv("MARKET_SCANNER_API_URL", "https://scanner.test")
    monkeypatch.setenv("SUGGESTION_HASH_SECRET", "test-secret")
    monkeypatch.setenv("MOMENTUM_API_USE_IAM", "true")

    settings = Settings(_env_file=None)

    assert settings.MOMENTUM_API_USE_IAM is True
