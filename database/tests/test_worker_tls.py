"""Real TLS handshakes through packaged worker engines, without cloud access."""

import importlib.util
import os
from pathlib import Path
import subprocess
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


@pytest.fixture(scope="module")
def tls_server(tmp_path_factory):
    spec = importlib.util.spec_from_file_location(
        "tls_domains", ROOT / "database/testing/local_domains.py"
    )
    domains = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(domains)
    domains.NAME = "deepcopy-worker-tls-test"
    domains.PORT = "55473"
    domains.LABEL = "org.deepcopy.worker-tls-test"
    if domains.inspect_container():
        pytest.fail("TLS fixture already exists; do not replace another running test")
    files = tmp_path_factory.mktemp("postgres-tls")
    for name in ("server", "untrusted"):
        run(
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-keyout",
            str(files / (name + ".key")),
            "-out",
            str(files / (name + ".pem")),
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
        )
    run(
        "docker",
        "create",
        "--name",
        domains.NAME,
        "--label",
        domains.LABEL + "=true",
        "--publish",
        "127.0.0.1:55473:5432",
        "--env",
        "POSTGRES_PASSWORD=domain-test-only",
        domains.IMAGE,
        "bash",
        "-c",
        "chown postgres:postgres /tmp/server.*; "
        "chmod 600 /tmp/server.key; exec docker-entrypoint.sh postgres "
        "-c ssl=on -c ssl_cert_file=/tmp/server.pem -c ssl_key_file=/tmp/server.key",
    )
    try:
        for extension in ("pem", "key"):
            run(
                "docker",
                "cp",
                str(files / ("server." + extension)),
                domains.NAME + ":/tmp/server." + extension,
            )
        run("docker", "start", domains.NAME)
        for _ in range(60):
            result = subprocess.run(
                ["docker", "exec", domains.NAME, "pg_isready", "-U", "postgres"],
                capture_output=True,
            )
            if result.returncode == 0:
                break
            time.sleep(0.25)
        else:
            pytest.fail(
                "TLS fixture did not become ready: "
                + run("docker", "logs", domains.NAME)
            )
        domains.reset()
        yield files
    finally:
        run("docker", "rm", "--force", domains.NAME)


@pytest.mark.parametrize("component", ["scanner"])
@pytest.mark.parametrize("kind", ["result", "session"])
@pytest.mark.parametrize("case", ["trusted", "wrong_ca", "wrong_hostname"])
def test_worker_verifies_tls(tls_server, component, case, kind):
    project = "market-scanner-adk" if component == "scanner" else "momentum-adk"
    domain = "market_scanner" if component == "scanner" else "momentum"
    hostname = "127.0.0.1" if case == "wrong_hostname" else "localhost"
    ca = tls_server / ("untrusted.pem" if case == "wrong_ca" else "server.pem")
    url = f"postgresql://database_migrator:domain-test-only@{hostname}:55473/{domain}?sslmode=verify-full&sslrootcert={ca}"
    result = subprocess.run(
        [
            str(ROOT / "apps/backend" / project / ".venv/bin/python"),
            str(ROOT / "database/testing/tls_probe.py"),
            component,
            kind,
            url,
        ],
        env={**os.environ, "DATABASE_CA_FILE": str(ca)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    if case == "trusted":
        assert result.returncode == 0, result.stdout + result.stderr
        assert "verified TLS" in result.stdout
    else:
        assert result.returncode == 1, result.stdout + result.stderr
        assert "SSLCertVerificationError" in result.stdout
        assert "domain-test-only" not in result.stdout + result.stderr
