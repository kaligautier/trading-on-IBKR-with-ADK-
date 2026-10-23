"""Manage ONLY the dedicated disposable local domain test container."""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "deepcopy-domains-test"
LABEL = "org.deepcopy.domain-tests"
PASSWORD = "domain-test-only"
PORT = "55461"
DOMAINS = ("market_scanner", "momentum")
IMAGE = (
    "postgres:17@sha256:"
    "d74eeac9a635390a49bc21bd49fccd973de707e2a53a76ac49b552b8712ec46f"
)


def run(*args, data=None, env=None):
    result = subprocess.run(
        args, input=data, text=True, capture_output=True, env=env, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr or result.stdout)
    return result.stdout


def inspect_container():
    endpoint = (
        os.getenv("DOCKER_HOST")
        or run(
            "docker",
            "context",
            "inspect",
            "--format",
            "{{.Endpoints.docker.Host}}",
        ).strip()
    )
    if not endpoint.startswith("unix://"):
        raise RuntimeError("Local tests require a local Unix-socket Docker daemon")
    listing = run("docker", "container", "ls", "-a", "--format", "{{.Names}}")
    if NAME not in listing.splitlines():
        return None
    info = json.loads(run("docker", "inspect", NAME))[0]
    ports = info["HostConfig"]["PortBindings"].get("5432/tcp", [])
    if info["Config"]["Labels"].get(LABEL) != "true" or ports != [
        {"HostIp": "127.0.0.1", "HostPort": PORT}
    ]:
        raise RuntimeError("Refusing a foreign or non-loopback test container")
    return info


def start():
    info = inspect_container()
    if info:
        if not info["State"]["Running"]:
            raise RuntimeError("Owned test container is stopped; inspect it explicitly")
        return
    run(
        "docker",
        "run",
        "--detach",
        "--rm",
        "--name",
        NAME,
        "--label",
        f"{LABEL}=true",
        "--publish",
        f"127.0.0.1:{PORT}:5432",
        "--env",
        f"POSTGRES_PASSWORD={PASSWORD}",
        IMAGE,
    )
    for _ in range(60):
        ready = subprocess.run(
            ["docker", "exec", NAME, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
            capture_output=True,
        )
        if ready.returncode == 0:
            return
        time.sleep(0.5)
    raise RuntimeError("Disposable PostgreSQL did not become ready")


def sql(database, statement, *variables):
    return run(
        "docker",
        "exec",
        "-i",
        NAME,
        "psql",
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "postgres",
        "-d",
        database,
        *variables,
        data=statement,
    )


def migrate(domain, command="update"):
    if domain not in DOMAINS or not inspect_container():
        raise ValueError("Unknown domain or missing owned container")
    changelog = "scanner" if domain == "market_scanner" else "momentum"
    environment = {
        **os.environ,
        "LIQUIBASE_COMMAND_URL": f"jdbc:postgresql://127.0.0.1:5432/{domain}",
        "LIQUIBASE_COMMAND_USERNAME": "database_migrator",
        "LIQUIBASE_COMMAND_PASSWORD": PASSWORD,
        "LIQUIBASE_COMMAND_CHANGELOG_FILE": f"db.changelog-{changelog}.yaml",
        "LIQUIBASE_LIQUIBASE_SCHEMA_NAME": "liquibase",
    }
    output = run(
        "docker",
        "run",
        "--rm",
        "--network",
        f"container:{NAME}",
        "--volume",
        f"{ROOT / 'changelog'}:/liquibase/changelog:ro",
        *[
            arg
            for key in environment
            if key.startswith("LIQUIBASE_")
            for arg in ("--env", key)
        ],
        "local/deep-copy-liquibase:5.0.4",
        command,
        env=environment,
    )
    return output


def reset():
    start()
    # This container belongs exclusively to this harness, never another project.
    run("docker", "build", "--tag", "local/deep-copy-liquibase:5.0.4", str(ROOT))
    for role, limit in (
        ("database_migrator", 2),
        ("market_scanner_writer", 4),
        ("market_scanner_reader", 4),
        ("momentum_sessions_writer", 4),
        ("momentum_results_writer", 4),
    ):
        sql(
            "postgres",
            f"""
DO $$ BEGIN
IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{role}') THEN
  CREATE ROLE {role} LOGIN NOINHERIT PASSWORD '{PASSWORD}' CONNECTION LIMIT {limit};
END IF;
END $$;
ALTER ROLE {role} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS
    CONNECTION LIMIT {limit};
""",
        )
    for domain in DOMAINS:
        sql("postgres", f'DROP DATABASE IF EXISTS "{domain}" WITH (FORCE);')
        sql("postgres", f'CREATE DATABASE "{domain}";')
        sql(
            domain,
            (ROOT / "domain-bootstrap.sql").read_text(),
            "-v",
            f"domain={domain}",
        )
        migrate(domain, "validate")
        migrate(domain)
        migrate(domain)
    print("Fresh domain schemas validated; repeated update is a no-op.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "reset", "stop", "migrate"))
    parser.add_argument("--domain", choices=DOMAINS)
    args = parser.parse_args()
    if args.action == "start":
        start()
    elif args.action == "reset":
        reset()
    elif args.action == "stop":
        if inspect_container():
            run("docker", "stop", NAME)
    else:
        if not args.domain:
            parser.error("migrate requires --domain")
        migrate(args.domain)


if __name__ == "__main__":
    main()
