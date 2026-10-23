"""Rebuild and exercise only owned local fixtures, with independent Python processes."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import local_domains as domains

ROOT = Path(__file__).resolve().parents[2]


def execute(args, *, cwd=ROOT, environment=None):
    result = subprocess.run(
        args,
        cwd=cwd,
        env={**os.environ, "TZ": "UTC", "PGSSLMODE": "disable", **(environment or {})},
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    print(result.stdout, flush=True)


def fixture(name, port, label):
    domains.inspect_container()  # Reject remote Docker endpoints before mutations.
    existing = domains.run("docker", "ps", "-a", "--format", "{{.Names}}")
    if name in existing.splitlines():
        info = json.loads(domains.run("docker", "inspect", name))[0]
        if info["Config"]["Labels"].get(label) != "true" or info["HostConfig"][
            "PortBindings"
        ].get("5432/tcp") != [{"HostIp": "127.0.0.1", "HostPort": port}]:
            raise RuntimeError("Refusing a foreign regression-test container")
        domains.run("docker", "stop", name)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", int(port)))
    domains.run(
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        name,
        "--label",
        f"{label}=true",
        "--publish",
        f"127.0.0.1:{port}:5432",
        "--env",
        "POSTGRES_PASSWORD=local-test-only",
        domains.IMAGE,
    )
    for _ in range(60):
        ready = subprocess.run(
            ["docker", "exec", name, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
            capture_output=True,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("Local regression PostgreSQL did not start")


def test(component, environment, *paths):
    execute(
        ["uv", "run", "--frozen", "pytest", "-q", "--tb=short", *paths],
        cwd=component,
        environment=environment,
    )


def main():
    scanner = ROOT / "apps/backend/market-scanner-adk"
    reader = ROOT / "apps/backend/market-scanner-api"
    execute(
        [
            "uv",
            "run",
            "--project",
            str(scanner),
            "--frozen",
            "python",
            "-m",
            "pytest",
            "-q",
            "-c",
            "database/pytest.ini",
            "--confcutdir=database/tests",
            "database/tests",
        ]
    )  # The foundation suite explicitly resets only the owned domain fixture.
    name = "deepcopy-current-scanner-tests"
    fixture(name, "55466", "org.deepcopy.scanner-tests")
    try:
        test(
            scanner,
            {
                "RUN_DOMAIN_TESTS": "1",
                "MARKET_SHARED_TEST_DATABASE_URL": "postgresql://postgres:local-test-only@127.0.0.1:55466/postgres",
                "MARKET_SHARED_TEST_CONTAINER": name,
            },
            "src/test",
        )
        domains.run(
            "docker", "exec", name, "createdb", "-U", "postgres", "scanner_reader_test"
        )
        test(
            reader,
            {
                "RUN_DOMAIN_TESTS": "1",
                "TEST_DATABASE_URL": "postgresql://postgres:local-test-only@127.0.0.1:55466/scanner_reader_test",
            },
            "src/test",
        )
    finally:
        domains.run("docker", "stop", name)
    momentum = ROOT / "apps/backend/momentum-adk"
    test(momentum, {}, "tests/unit")
    execute(["bash", str(momentum / "scripts/test_database.sh"), "start"])
    try:
        test(
            momentum,
            {
                "MOMENTUM_TEST_ADMIN_URL": "postgresql://postgres:local-test-only@127.0.0.1:55467/postgres",
                "MOMENTUM_TEST_CONTAINER": "momentum-current-test-db",
            },
            "tests/integration",
        )
    finally:
        execute(["bash", str(momentum / "scripts/test_database.sh"), "stop"])

    execute(
        [
            "bash",
            str(ROOT / "apps/backend/momentum-api/scripts/test_database.sh"),
            "verify",
        ]
    )
    print("Local rehearsal passed. Domain databases remain on 127.0.0.1:55471.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from None
