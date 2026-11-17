"""The runtime owns the pool through lifespan, without a database call for liveness."""

import json
import logging
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config.settings import Settings
from app.main import create_app
from app.observability import LOGGER


def runtime_settings():
    return Settings(
        _env_file=None,
        AUTH_MODE="token",
        DATABASE_POOL_SIZE=1,
        DATABASE_POOL_TIMEOUT=5,
        DATABASE_URL="postgresql://momentum_results_reader:unused@localhost/momentum",
        API_TOKEN="disposable-runtime-token",
    )


@pytest.fixture(autouse=True)
def isolated_logger():
    before = LOGGER.handlers[:], LOGGER.level, LOGGER.propagate
    diagnostic_output = logging.raiseExceptions
    try:
        yield
    finally:
        LOGGER.handlers, LOGGER.level, LOGGER.propagate = before
        logging.raiseExceptions = diagnostic_output


def test_runtime_factory_lifespan_and_safe_logging(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("DATABASE_POOL_SIZE=99\nAUTH_MODE=invalid\n")
    monkeypatch.setenv("DATABASE_URL", "invalid ambient configuration")
    app = create_app(runtime_settings())
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        engine = app.state.service.repository.engine
        assert engine.pool.checkedout() == 0
    event = json.loads(capsys.readouterr().err.strip())
    assert event["request_id"] == response.headers["request-id"]


@pytest.mark.parametrize("primary_failure", [False, True])
async def test_pool_cleanup_preserves_the_primary_failure(
    monkeypatch, capsys, primary_failure
):
    engine = AsyncMock()
    cleanup = RuntimeError("private cleanup details")
    engine.dispose.side_effect = cleanup
    monkeypatch.setattr(main, "create_engine", lambda _: engine)
    app = create_app(runtime_settings())
    primary = ValueError("private primary details")
    expected = ValueError if primary_failure else RuntimeError
    with pytest.raises(expected) as caught:
        async with app.router.lifespan_context(app):
            if primary_failure:
                raise primary
    assert caught.value is (primary if primary_failure else cleanup)
    engine.dispose.assert_awaited_once()
    output = capsys.readouterr().err
    if primary_failure:
        assert json.loads(output)["event"] == "storage_cleanup_failed"
    assert "private" not in output


def test_real_logging_handler_failure_does_not_print_exception_chains(capsys):
    class BrokenStream:
        def write(self, value):
            raise OSError("private log transport details")

        def flush(self):
            pass

    logging.raiseExceptions = True
    app = create_app(runtime_settings())
    LOGGER.handlers = [logging.StreamHandler(BrokenStream())]

    @app.get("/crash")
    async def crash():
        raise RuntimeError("private primary details")

    with TestClient(app) as client:
        response = client.get(
            "/crash", headers={"Authorization": "Bearer disposable-runtime-token"}
        )
    assert response.status_code == 500
    assert "private" not in response.text
    assert capsys.readouterr().err == ""
