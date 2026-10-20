"""Pytest configuration and shared fixtures for unit tests."""

from unittest.mock import MagicMock

import pytest
from google.adk.tools import ToolContext


@pytest.fixture
def mock_tool_context():
    """Mock ToolContext for testing ADK tools."""
    context = MagicMock(spec=ToolContext)
    context.state = {}
    return context


@pytest.fixture(autouse=True)
def unit_session_store(monkeypatch):
    """Unit tests isolate I/O; integration tests exercise the real PostgreSQL store."""
    from google.adk.sessions import InMemorySessionService

    from app import application
    from app.jobs import daily_scan

    class UnitSessionService(InMemorySessionService):
        def __init__(self, _url):
            super().__init__()

        async def prepare_tables(self):
            pass

        async def close(self):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_exc):
            await self.close()

    monkeypatch.setattr(application, "ScannerSessionService", UnitSessionService)
    monkeypatch.setattr(daily_scan, "ScannerSessionService", UnitSessionService)
