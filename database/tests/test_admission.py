"""Independent worker processes exercise lock ownership, cancellation and crash cleanup."""

import importlib.util
import os
from pathlib import Path
import select
import subprocess
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def admission_server():
    spec = importlib.util.spec_from_file_location(
        "admission_domains", ROOT / "database/testing/local_domains.py"
    )
    domains = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(domains)
    domains.NAME, domains.PORT = "deepcopy-admission-test", "55474"
    domains.LABEL = "org.deepcopy.admission-test"
    if domains.inspect_container():
        pytest.fail("Admission fixture exists; refusing to replace another run")
    domains.run(
        "docker",
        "run",
        "--rm",
        "-d",
        "--name",
        domains.NAME,
        "--label",
        domains.LABEL + "=true",
        "-p",
        "127.0.0.1:55474:5432",
        "-e",
        "POSTGRES_PASSWORD=domain-test-only",
        domains.IMAGE,
        "-c",
        "max_connections=15",
        "-c",
        "superuser_reserved_connections=3",
    )
    try:
        for _ in range(60):
            ready = subprocess.run(
                [
                    "docker",
                    "exec",
                    domains.NAME,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "postgres",
                ],
                capture_output=True,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.1)
        for domain, role in (
            ("market_scanner", "market_scanner_writer"),
            ("momentum", "momentum_results_writer"),
        ):
            domains.sql(
                "postgres",
                f"CREATE DATABASE {domain}; CREATE ROLE {role} LOGIN PASSWORD 'domain-test-only' CONNECTION LIMIT 2;",
            )
        yield domains
    finally:
        domains.run("docker", "stop", domains.NAME)


def launch(component, mode):
    application = (
        ROOT
        / "apps/backend"
        / ("market-scanner-adk" if component == "scanner" else "momentum-adk")
    )
    role, domain = (
        ("market_scanner_writer", "market_scanner")
        if component == "scanner"
        else ("momentum_results_writer", "momentum")
    )
    return subprocess.Popen(
        [
            str(application / ".venv/bin/python"),
            str(ROOT / "database/testing/admission_probe.py"),
            component,
            mode,
        ],
        cwd=application,
        env={
            **os.environ,
            "PYTHONPATH": str(
                application / "src" if component == "scanner" else application
            ),
            "PROBE_URL": f"postgresql://{role}:domain-test-only@127.0.0.1:55474/{domain}",
            "GOOGLE_CLOUD_PROJECT": "local-admission",
        },
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def line(process):
    assert select.select([process.stdout], [], [], 20)[0], (
        "Admission did not finish promptly"
    )
    result = process.stdout.readline().strip()
    if not result:
        _, errors = process.communicate(timeout=5)
        pytest.fail(errors)
    return result


@pytest.mark.parametrize("component", ["scanner"])
@pytest.mark.parametrize("ending", ["normal", "crash"])
def test_competing_process_is_busy_then_recovers(admission_server, component, ending):
    owner = launch(component, "hold")
    try:
        assert line(owner) == "acquired"
        contender = launch(component, "write")
        output, errors = contender.communicate(timeout=20)
        assert contender.returncode == 75, errors
        assert output.strip() == "busy"
        if ending == "crash":
            owner.kill()
        else:
            owner.stdin.write("done\n")
            owner.stdin.flush()
        owner.communicate(timeout=20)
        successor = launch(component, "cancel")
        output, errors = successor.communicate(timeout=20)
        assert successor.returncode == 0, errors
        assert output.splitlines() == ["acquired", "cancelled"]
        final = launch(component, "write")
        output, errors = final.communicate(timeout=20)
        assert final.returncode == 0, errors
        assert output.strip() == "acquired"
    finally:
        if owner.poll() is None:
            owner.kill()
        owner.communicate(timeout=20)
