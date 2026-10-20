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
        "postgresql://postgres:local@remote.example:55449/postgres",
        "postgresql://postgres:local@127.0.0.1:5432/postgres",
        "postgresql://other:local@127.0.0.1:55449/postgres",
        "https://127.0.0.1:55449/postgres",
        "postgresql://postgres:local@127.0.0.1:55449/postgres?host=remote.example",
        "postgresql://postgres:local@127.0.0.1:55449/another_database",
        "postgresql://postgres:local@127.0.0.1:55449/postgres#fragment",
        "",
    ],
)
def test_fixture_rejects_non_disposable_targets(harness, url):
    with pytest.raises(ValueError):
        harness.local_target(url, "momentum-test-db")


def test_fixture_requires_its_named_container(harness):
    url = "postgresql://postgres:local@127.0.0.1:55449/postgres"
    with pytest.raises(ValueError):
        harness.local_target(url, "another-container")
    assert harness.local_target(url, "momentum-test-db").port == 55449
