"""Protect live targets and reject schema drift before baseline adoption."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def management():
    spec = importlib.util.spec_from_file_location(
        "database_management", ROOT / "manage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://database_migrator:fixture@remote.example/momentum",
        "postgresql://database_migrator:fixture@remote.example/momentum?sslmode=require",
        "postgresql://database_migrator:fixture@localhost/market_scanner",
        "postgresql://database_migrator:fixture@localhost/momentum?host=remote.example",
    ],
)
def test_reject_wrong_database_or_unverified_remote_tls(management, url):
    with pytest.raises(ValueError):
        management.connection_parameters(url, "momentum", None)


def test_local_target_does_not_need_tls(management):
    parameters = management.connection_parameters(
        "postgresql://database_migrator:fixture@127.0.0.1:55463/momentum",
        "momentum",
        None,
    )
    assert parameters["database"] == "momentum"
    assert parameters["ssl"] is False


def test_schema_drift_is_rejected_before_adoption(management):
    with pytest.raises(ValueError, match="differs"):
        management.require_baseline({"tables": ["unexpected"]}, "0" * 64)


def test_fingerprint_is_independent_of_mapping_order(management):
    from operations.catalog import fingerprint

    assert fingerprint({"tables": [], "schemas": []}) == fingerprint(
        {"schemas": [], "tables": []}
    )


def test_status_reports_pending_changes_without_connection_details(
    management, monkeypatch, capsys
):
    from types import SimpleNamespace

    monkeypatch.setattr(
        management.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stderr="",
            stdout="1 changeset has not been applied to role@jdbc:postgresql://private-host/momentum\n"
            "  domains/momentum/changelog.yaml::next-change::deepcopy\n",
        ),
    )
    management.liquibase(
        "momentum",
        dict(
            host="localhost",
            port=5432,
            user="database_migrator",
            password="fixture",
            ssl=False,
        ),
        ["status", "--verbose"],
    )
    assert (
        capsys.readouterr().out
        == "1 changeset has not been applied\ndomains/momentum/changelog.yaml::next-change::deepcopy\n"
    )
