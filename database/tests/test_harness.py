"""Refuse foreign fixtures or remote Docker before any destructive statement."""

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def harness():
    path = Path(__file__).resolve().parents[1] / "testing/local_domains.py"
    spec = importlib.util.spec_from_file_location("local_domains", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reject_remote_docker(harness, monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example:2375")
    monkeypatch.setattr(harness, "run", lambda *_: pytest.fail("Docker must not run"))
    with pytest.raises(RuntimeError, match="local Unix-socket"):
        harness.inspect_container()


@pytest.mark.parametrize("label,host", [("false", "127.0.0.1"), ("true", "0.0.0.0")])
def test_reject_foreign_container_or_public_port(harness, monkeypatch, label, host):
    monkeypatch.setenv("DOCKER_HOST", "unix:///local-fixture.sock")
    calls = iter(
        [
            harness.NAME,
            json.dumps(
                [
                    {
                        "Config": {"Labels": {harness.LABEL: label}},
                        "HostConfig": {
                            "PortBindings": {
                                "5432/tcp": [
                                    {"HostIp": host, "HostPort": harness.PORT}
                                ],
                            }
                        },
                    }
                ]
            ),
        ]
    )
    monkeypatch.setattr(harness, "run", lambda *_: next(calls))
    with pytest.raises(RuntimeError, match="foreign or non-loopback"):
        harness.inspect_container()


def test_reject_unknown_domain_before_docker(harness, monkeypatch):
    monkeypatch.setattr(harness, "run", lambda *_: pytest.fail("Docker must not run"))
    with pytest.raises(ValueError, match="Unknown domain"):
        harness.migrate("defaultdb")
