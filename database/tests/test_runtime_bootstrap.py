"""Current bootstraps reject unusable and elevated logins atomically."""

import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def docker(*args, **kwargs):
    return subprocess.run(["docker", *args], capture_output=True, **kwargs)


@pytest.fixture(scope="module")
def postgres():
    endpoint = (
        os.getenv("DOCKER_HOST")
        or subprocess.check_output(
            ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
            text=True,
        ).strip()
    )
    assert endpoint.startswith("unix://"), "Local Docker is required"
    name = "bootstrap-roles-" + uuid.uuid4().hex
    image = "postgres:18@sha256:74935e72241653ca55e0414067e6d8763aceb8a810eb51b452253ec3dcfc4336"
    docker(
        "run",
        "--rm",
        "-d",
        "--name",
        name,
        "-e",
        "POSTGRES_PASSWORD=local-only",
        image,
        check=True,
    )
    try:
        for _ in range(60):
            ready = docker(
                "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            pytest.fail("Disposable PostgreSQL did not start")

        def sql(database, statement):
            return docker(
                "exec",
                "-i",
                name,
                "psql",
                "-XAt",
                "-v",
                "ON_ERROR_STOP=1",
                "-U",
                "postgres",
                "-d",
                database,
                input=statement,
                text=True,
            )

        setup = "CREATE ROLE database_migrator LOGIN; REVOKE CONNECT ON DATABASE postgres, template1 FROM PUBLIC;"
        for domain in ("market_scanner", "momentum"):
            setup += f"CREATE DATABASE {domain}; REVOKE CONNECT ON DATABASE {domain} FROM PUBLIC;"
        for role in (
            "market_scanner_writer",
            "market_scanner_reader",
            "momentum_sessions_writer",
            "momentum_results_writer",
            "momentum_results_reader",
        ):
            setup += f"CREATE ROLE {role} LOGIN;"
        assert sql("postgres", setup).returncode == 0
        yield sql
    finally:
        docker("stop", name, check=True)


@pytest.mark.parametrize(
    "domain,role",
    [
        ("market_scanner", "market_scanner_writer"),
        ("market_scanner", "market_scanner_reader"),
        ("momentum", "momentum_sessions_writer"),
        ("momentum", "momentum_results_writer"),
        ("momentum", "momentum_results_reader"),
    ],
)
@pytest.mark.parametrize("attribute", ["NOLOGIN", "REPLICATION"])
def test_bootstrap_rejects_unsafe_runtime_role(postgres, domain, role, attribute):
    bootstrap = (ROOT / "domains" / domain / "bootstrap.sql").read_text()
    assert postgres("postgres", f"ALTER ROLE {role} {attribute}").returncode == 0
    try:
        rejected = postgres(domain, bootstrap)
        assert rejected.returncode != 0
        assert "runtime" in rejected.stderr.lower()
    finally:
        assert (
            postgres("postgres", f"ALTER ROLE {role} LOGIN NOREPLICATION").returncode
            == 0
        )
    assert postgres(domain, bootstrap).returncode == 0
