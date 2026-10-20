import pytest

from app.job_runner import database_address, main


@pytest.mark.parametrize("url", ["sqlite:///file", "postgresql://u:p@host/defaultdb"])
def test_worker_rejects_wrong_database(url):
    with pytest.raises(ValueError):
        database_address(url)


def test_worker_preserves_explicit_database_and_ssl():
    address = database_address("postgres://u:p@host/momentum?sslmode=require")
    assert address.drivername == "postgresql+asyncpg"
    assert address.database == "momentum"
    assert address.query["ssl"] == "require"


def test_worker_fails_without_echoing_invalid_request(monkeypatch, capsys):
    monkeypatch.setenv("TA_ANALYSIS_REQUEST", "private-marker")
    assert main() == 1
    output = capsys.readouterr().out
    assert "momentum_failed" in output
    assert "private-marker" not in output
