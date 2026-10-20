"""Rebuild and exercise only owned local fixtures, with independent Python processes."""

import argparse
import json
import os
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
        env={**os.environ, "TZ": "UTC", **(environment or {})},
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
            ["docker", "exec", name, "pg_isready", "-U", "postgres"],
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--momentum-root", type=Path)
    args = parser.parse_args()
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
    name = "deepcopy-scanner-tests"
    fixture(name, "55462", "org.deepcopy.scanner-tests")
    try:
        test(
            scanner,
            {
                "RUN_DOMAIN_TESTS": "1",
                "MARKET_SHARED_TEST_DATABASE_URL": "postgresql://postgres:local-test-only@127.0.0.1:55462/postgres",
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
                "TEST_DATABASE_URL": "postgresql://postgres:local-test-only@127.0.0.1:55462/scanner_reader_test",
            },
            "src/test",
        )
    finally:
        domains.run("docker", "stop", name)
    momentum = (args.momentum_root or ROOT) / "apps/backend/momentum-adk"
    if momentum.exists():
        test(momentum, {}, "tests/unit")
        execute(
            [
                "uv",
                "run",
                "--project",
                str(momentum.resolve()),
                "--frozen",
                "python",
                "-m",
                "pytest",
                "-q",
                "--tb=short",
                "-c",
                "database/pytest.ini",
                "--confcutdir=database/momentum_tests",
                "database/momentum_tests",
            ],
            environment={"MOMENTUM_ROOT": str(momentum.resolve())},
        )
    elif args.momentum_root:
        raise RuntimeError("The supplied Momentum worktree has no application package")
    else:
        print(
            "Momentum SDK/schema verified; adapter package absent from this branch. "
            "Use --momentum-root for its separate worktree."
        )
    print("Local rehearsal passed. Domain databases remain on 127.0.0.1:55461.")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from None
