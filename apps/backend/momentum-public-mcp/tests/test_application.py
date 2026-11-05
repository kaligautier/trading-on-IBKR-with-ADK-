"""Cloud Run runtime configuration tests."""

import pytest
from fastmcp import Client

from app.application import MomentumPublicApplication
from app.config.config import Settings
from app.config.constants import PUBLIC_TOOL_NAMES


def test_cloud_run_identity_is_enabled_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("MOMENTUM_API_URL", "https://momentum.test")
    monkeypatch.setenv("MARKET_SCANNER_API_URL", "https://scanner.test")
    monkeypatch.setenv("SUGGESTION_HASH_SECRET", "test-secret")
    monkeypatch.setenv("MOMENTUM_API_USE_IAM", "true")

    settings = Settings(_env_file=None)

    assert settings.MOMENTUM_API_USE_IAM is True


@pytest.mark.parametrize("page_size", [1, 2, 4, 100])
async def test_discovery_uses_configured_page_size(monkeypatch, page_size):
    monkeypatch.setenv("DEFAULT_PAGE_SIZE", str(page_size))
    settings = Settings(
        _env_file=None,
        SUGGESTION_HASH_SECRET="test-signing-key",
        MOMENTUM_API_URL="https://momentum.test",
        MARKET_SCANNER_API_URL="https://scanner.test",
        MOMENTUM_API_USE_IAM=False,
    )
    application = MomentumPublicApplication(settings)
    names = []
    cursors = set()

    async with Client(application.mcp) as client:
        page = await client.list_tools_mcp()
        while True:
            remaining = len(PUBLIC_TOOL_NAMES) - len(names)
            assert len(page.tools) == min(page_size, remaining)
            names.extend(tool.name for tool in page.tools)
            if len(names) == len(PUBLIC_TOOL_NAMES):
                assert page.next_cursor is None
                break
            assert page.next_cursor
            assert page.next_cursor not in cursors
            cursors.add(page.next_cursor)
            page = await client.list_tools_mcp(cursor=page.next_cursor)

        automatic = await client.list_tools()

    assert len(names) == len(set(names))
    assert set(names) == PUBLIC_TOOL_NAMES
    assert [tool.name for tool in automatic] == names


@pytest.mark.parametrize("fails", [False, True])
def test_main_initializes_telemetry_before_logging_and_closes_it(monkeypatch, fails):
    import runpy
    from types import SimpleNamespace

    from app import application
    from app.config import config
    from app.observability import logger, telemetry

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
    module = runpy.run_module("app.main", run_name="test_entrypoint")
    assert events == ["telemetry", "logging", "application"]
    if fails:
        with pytest.raises(RuntimeError, match="server stopped"):
            module["main"]()
    else:
        module["main"]()
    assert events == ["telemetry", "logging", "application", "run", "shutdown"]
