"""The destructive fixture must reject any target outside its local container."""

import importlib.util

import pytest


@pytest.fixture
def harness(project_root):
    spec = importlib.util.spec_from_file_location(
        "database_harness", project_root / "tests/integration/conftest.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://postgres:local@remote.example:55467/postgres",
        "postgresql://postgres:local@127.0.0.1:5432/postgres",
        "postgresql://other:local@127.0.0.1:55467/postgres",
        "https://127.0.0.1:55467/postgres",
        "postgresql://postgres:local@127.0.0.1:55467/postgres?host=remote.example",
        "postgresql://postgres:local@127.0.0.1:55467/another_database",
        "postgresql://postgres:local@127.0.0.1:55467/postgres#fragment",
        "",
    ],
)
def test_fixture_rejects_non_disposable_targets(harness, url):
    with pytest.raises(ValueError):
        harness.local_target(url, "momentum-current-test-db")


def test_fixture_requires_its_named_container(harness):
    url = "postgresql://postgres:local@127.0.0.1:55467/postgres"
    with pytest.raises(ValueError):
        harness.local_target(url, "another-container")
    assert harness.local_target(url, "momentum-current-test-db").port == 55467


@pytest.mark.parametrize("running,ports", [(False, None), (True, None)])
def test_fixture_rejects_inactive_container_before_connecting(
    harness, monkeypatch, running, ports
):
    import json

    binding = {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(harness.PORT)}]}
    metadata = {
        "Config": {"Labels": {"org.deepcopy.momentum-test": "true"}},
        "HostConfig": {"PortBindings": binding},
        "State": {"Running": running},
        "NetworkSettings": {"Ports": ports or {}},
    }
    monkeypatch.setenv(
        "MOMENTUM_TEST_ADMIN_URL",
        "postgresql://postgres:local@127.0.0.1:55467/postgres",
    )
    monkeypatch.setenv("MOMENTUM_TEST_CONTAINER", harness.CONTAINER)
    monkeypatch.setattr(
        harness.subprocess, "check_output", lambda *a, **k: json.dumps([metadata])
    )
    monkeypatch.setattr(
        harness.asyncpg, "connect", lambda *a, **k: pytest.fail("Must not connect")
    )
    fixture = harness.domain_database.__wrapped__(None)
    with pytest.raises(pytest.fail.Exception, match="stopped or inactive"):
        next(fixture)
