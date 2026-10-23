import pytest

from app.infrastructure.postgres_tls import connection_options
from app.job_runner import main


@pytest.mark.parametrize("url", ["sqlite:///file", "postgresql://u:p@host/defaultdb"])
def test_worker_rejects_wrong_database(url):
    with pytest.raises(ValueError):
        connection_options(url)


def test_worker_preserves_explicit_database_and_ssl():
    address, tls = connection_options(
        "postgres://u:p@host/momentum?sslmode=verify-full"
    )
    assert address.drivername == "postgresql+asyncpg"
    assert address.database == "momentum"
    assert address.query == {}
    assert tls.check_hostname


def test_worker_fails_without_echoing_invalid_request(monkeypatch, capsys):
    monkeypatch.setenv("TA_ANALYSIS_REQUEST", "private-marker")
    assert main() == 1
    output = capsys.readouterr().out
    assert "momentum_failed" in output
    assert "private-marker" not in output


@pytest.mark.asyncio
@pytest.mark.parametrize("save_fails", [True, False])
async def test_worker_uses_one_completion_transaction(monkeypatch, save_fails):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    from app import job_runner
    from app.domain.contracts import AnalysisRequest, WorkflowExecution, WorkflowResult

    request = AnalysisRequest(
        ticker="AAPL",
        analysis_date="2026-10-21",
        requested_by="test",
        session_id="d33d8f79-6a90-4aad-a7d7-d990ed341c47",
    )
    result = WorkflowResult(
        ticker="AAPL",
        analysis_date="2026-10-21",
        signal="Hold",
        final_decision="Hold",
        structured={},
        reports={},
    )
    execution = WorkflowExecution(
        result=result,
        user_id="system",
        session_id=str(request.session_id),
        invocation_id="test",
    )
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def admitted(_engine):
        yield object()

    monkeypatch.setattr(job_runner, "admit_execution", admitted)
    order = []
    memory = Mock()
    memory.prepare = AsyncMock(return_value=request)
    runtime = SimpleNamespace(
        engine=SimpleNamespace(execute=AsyncMock(return_value=execution)),
        session_service=SimpleNamespace(close=AsyncMock()),
    )
    monkeypatch.setenv(
        "MOMENTUM_SESSION_DATABASE_URL", "postgres://u:p@localhost/momentum"
    )
    monkeypatch.setenv(
        "MOMENTUM_RESULT_DATABASE_URL", "postgres://u:p@localhost/momentum"
    )
    monkeypatch.setattr(job_runner, "Settings", Mock(return_value=Mock()))
    monkeypatch.setattr(
        job_runner, "create_model", Mock(return_value=SimpleNamespace())
    )
    monkeypatch.setattr(
        job_runner,
        "create_async_engine",
        Mock(return_value=SimpleNamespace(dispose=AsyncMock())),
    )
    monkeypatch.setattr(job_runner, "async_sessionmaker", Mock())
    monkeypatch.setattr(
        job_runner,
        "MomentumRuntimeFactory",
        lambda *args: SimpleNamespace(create=AsyncMock(return_value=runtime)),
    )
    monkeypatch.setattr(job_runner, "PostgresMemoryRepository", Mock())
    monkeypatch.setattr(job_runner, "TradingMemoryService", Mock(return_value=memory))

    async def save(value):
        assert value is execution
        assert order == []
        if save_fails:
            raise RuntimeError("database unavailable")
        order.append("commit")

    monkeypatch.setattr(
        job_runner, "PostgresResultRepository", lambda *args: SimpleNamespace(save=save)
    )
    if save_fails:
        with pytest.raises(RuntimeError, match="database unavailable"):
            await job_runner.execute(request)
        memory.complete.assert_not_called()
    else:
        await job_runner.execute(request)
        assert order == ["commit"]
        memory.complete.assert_not_called()


async def test_busy_worker_never_initializes_models_or_sessions(monkeypatch):
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock, Mock

    from app import job_runner
    from app.infrastructure.admission import MomentumBusyError

    @asynccontextmanager
    async def busy(_engine):
        raise MomentumBusyError()
        yield

    engine = Mock(dispose=AsyncMock())
    monkeypatch.setattr(job_runner, "Settings", Mock())
    monkeypatch.setattr(job_runner, "create_result_engine", Mock(return_value=engine))
    monkeypatch.setattr(job_runner, "admit_execution", busy)
    model = Mock()
    runtime = Mock()
    monkeypatch.setattr(job_runner, "create_model", model)
    monkeypatch.setattr(job_runner, "MomentumRuntimeFactory", runtime)
    monkeypatch.setenv(
        "MOMENTUM_SESSION_DATABASE_URL", "postgres://u:p@localhost/momentum"
    )
    monkeypatch.setenv(
        "MOMENTUM_RESULT_DATABASE_URL", "postgres://u:p@localhost/momentum"
    )
    with pytest.raises(MomentumBusyError):
        await job_runner.execute(Mock())
    model.assert_not_called()
    runtime.assert_not_called()
    engine.dispose.assert_awaited_once()
