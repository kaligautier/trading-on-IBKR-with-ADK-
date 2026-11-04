"""Cloud Run runtime configuration tests."""

import pytest

from momentum_public_mcp.config.config import Settings


def test_cloud_run_identity_is_enabled_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("MOMENTUM_API_URL", "https://momentum.test")
    monkeypatch.setenv("MARKET_SCANNER_API_URL", "https://scanner.test")
    monkeypatch.setenv("SUGGESTION_HASH_SECRET", "test-secret")
    monkeypatch.setenv("MOMENTUM_API_USE_IAM", "true")

    settings = Settings(_env_file=None)

    assert settings.MOMENTUM_API_USE_IAM is True


@pytest.mark.parametrize("fails", [False, True])
def test_main_initializes_telemetry_before_logging_and_closes_it(monkeypatch, fails):
    import runpy
    from types import SimpleNamespace

    from momentum_public_mcp import application
    from momentum_public_mcp.config import config
    from momentum_public_mcp.observability import logger, telemetry

    events = []
    settings = object()
    monkeypatch.setattr(config, "Settings", lambda: settings)

    def init(actual_settings):
        assert actual_settings is settings
        events.append("telemetry")
        return SimpleNamespace(shutdown=lambda: events.append("shutdown"))

    def logging_config(actual_settings):
        assert actual_settings is settings
        events.append("logging")

    def serve():
        events.append("run")
        if fails:
            raise RuntimeError("server stopped")

    def create(actual_settings):
        assert actual_settings is settings
        events.append("application")
        return SimpleNamespace(mcp=object(), run=serve)

    monkeypatch.setattr(telemetry, "init_telemetry", init)
    monkeypatch.setattr(logger, "config_logger", logging_config)
    monkeypatch.setattr(application, "MomentumPublicApplication", create)
    module = runpy.run_module("momentum_public_mcp.main", run_name="test_entrypoint")
    assert events == ["telemetry", "logging", "application"]
    if fails:
        with pytest.raises(RuntimeError, match="server stopped"):
            module["main"]()
    else:
        module["main"]()
    assert events == ["telemetry", "logging", "application", "run", "shutdown"]
