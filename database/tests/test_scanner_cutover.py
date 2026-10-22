"""Protect credential input and pre-delete target checks without cloud access."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit

import pytest


@pytest.fixture
def cutover_module():
    path = Path(__file__).resolve().parents[1] / "scripts/scanner_cutover.py"
    spec = importlib.util.spec_from_file_location("scanner_cutover", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o606])
def test_reject_readable_credentials(cutover_module, tmp_path, mode):
    path = tmp_path / ".env"
    path.write_text("TEST=fixture")
    path.chmod(mode)
    with pytest.raises(ValueError, match="private files"):
        cutover_module.private_config(path)


def test_reject_symlink_credentials(cutover_module, tmp_path):
    target = tmp_path / "target"
    target.write_text("TEST=fixture")
    target.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="private files"):
        cutover_module.private_config(link)
    assert cutover_module.private_config(target)["TEST"] == "fixture"


@pytest.mark.asyncio
async def test_cleanup_refuses_missing_new_report(cutover_module, tmp_path):
    (tmp_path / "verified-scan.json").write_text(
        '{"execution":"new-execution","scan_id":"new-report"}'
    )
    operation = object.__new__(cutover_module.Cutover)
    operation.args = SimpleNamespace(evidence=tmp_path)
    operation.verify_rollout = lambda: None
    connection = AsyncMock()
    connection.fetchval.return_value = False
    operation.connect = AsyncMock(return_value=connection)
    with pytest.raises(ValueError, match="must still exist"):
        await operation.cleanup()
    operation.connect.assert_awaited_once_with("market_scanner")
    connection.execute.assert_not_awaited()
    connection.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_never_connects_to_unrelated_database(cutover_module):
    operation = object.__new__(cutover_module.Cutover)
    with pytest.raises(ValueError, match="outside the reviewed scope"):
        await operation.connect("litellm", admin=True)


@pytest.mark.asyncio
async def test_decode_migration_password_for_database_client(
    cutover_module, monkeypatch
):
    operation = object.__new__(cutover_module.Cutover)
    operation.target = urlsplit(
        "postgresql://database_migrator:fixture%40%2B%3A@localhost:5432/defaultdb"
    )
    operation.tls = None
    connect = AsyncMock()
    monkeypatch.setattr(cutover_module.asyncpg, "connect", connect)
    await operation.connect("market_scanner")
    assert connect.call_args.kwargs["password"] == "fixture@+:"


def test_decode_liquibase_password_and_redact_both_forms(
    cutover_module, monkeypatch, tmp_path
):
    operation = object.__new__(cutover_module.Cutover)
    operation.target = urlsplit(
        "postgresql://database_migrator:fixture%40%2B%3A@localhost:5432/defaultdb"
    )
    operation.args = SimpleNamespace(evidence=tmp_path, ca=tmp_path / "ca.pem")

    def command(args, *, env):
        assert env["LIQUIBASE_COMMAND_PASSWORD"] == "fixture@+:"
        return (
            "CREATE TABLE _sessions.x;" * 5
            + "CREATE TABLE _analysis.x;" * 3
            + "fixture@+: fixture%40%2B%3A"
        )

    monkeypatch.setattr(cutover_module, "command", command)
    operation.migrate()
    for log in tmp_path.glob("*.log"):
        assert "fixture" not in log.read_text()


@pytest.mark.parametrize(
    "created,ready,observed,condition",
    [
        ("failed", "old", 2, "True"),
        ("new", "new", 1, "True"),
        ("new", "new", 2, "False"),
    ],
)
def test_rollout_requires_reconciled_ready_revision(
    cutover_module, monkeypatch, tmp_path, created, ready, observed, condition
):
    (tmp_path / "images.json").write_text("{}")
    operation = object.__new__(cutover_module.Cutover)
    operation.args = SimpleNamespace(evidence=tmp_path, gcp_project="fixture")
    service = {
        "metadata": {"generation": 2},
        "spec": {"template": {"spec": {}}},
        "status": {
            "latestCreatedRevisionName": created,
            "latestReadyRevisionName": ready,
            "observedGeneration": observed,
            "conditions": [{"type": "Ready", "status": condition}],
            "traffic": [{"revisionName": ready, "percent": 100}],
        },
    }
    monkeypatch.setattr(cutover_module, "command", lambda _: json.dumps(service))
    with pytest.raises(ValueError, match="not ready"):
        operation.verify_rollout()
