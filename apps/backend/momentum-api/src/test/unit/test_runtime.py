"""The runtime owns the pool through lifespan, without a database call for liveness."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.presentation.http.middleware import LOGGER


def test_runtime_factory_lifespan_and_safe_logging(monkeypatch, capsys):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://momentum_results_reader:unused@localhost/momentum"
    )
    monkeypatch.setenv("API_TOKEN", "disposable-runtime-token")
    before = LOGGER.handlers[:], LOGGER.level, LOGGER.propagate
    try:
        app = create_app()
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            engine = app.state.service.repository.engine
            assert engine.pool.checkedout() == 0
        assert response.headers["request-id"] in capsys.readouterr().err
    finally:
        LOGGER.handlers, LOGGER.level, LOGGER.propagate = before
