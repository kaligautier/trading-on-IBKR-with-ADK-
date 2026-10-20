"""Real Liquibase on an explicitly labeled, disposable local PostgreSQL server."""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest

DATABASE = Path(__file__).resolve().parents[5] / "database"
ROLES = (
    "database_migrator",
    "market_scanner_writer",
    "market_scanner_reader",
    "momentum_writer",
)


def local_target(url, container):
    address = urlsplit(url)
    if (
        address.scheme != "postgresql"
        or address.hostname != "127.0.0.1"
        or address.port != 55449
        or address.username != "postgres"
        or address.path != "/postgres"
        or address.query
        or address.fragment
        or container != "momentum-test-db"
    ):
        raise ValueError("Use the labeled disposable localhost PostgreSQL fixture")
    return address


def run_liquibase(url, *command, context="momentum"):
    address = urlsplit(url)
    environment = {
        **os.environ,
        "LIQUIBASE_COMMAND_URL": f"jdbc:postgresql://127.0.0.1:5432{address.path}",
        "LIQUIBASE_COMMAND_USERNAME": address.username,
        "LIQUIBASE_COMMAND_PASSWORD": address.password,
        "LIQUIBASE_COMMAND_CHANGELOG_FILE": "db.changelog-master.yaml",
        "LIQUIBASE_LIQUIBASE_SCHEMA_NAME": "liquibase",
    }
    if context is not None:
        environment["LIQUIBASE_COMMAND_CONTEXT_FILTER"] = context
    else:
        environment.pop("LIQUIBASE_COMMAND_CONTEXT_FILTER", None)
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "container:momentum-test-db",
            "--volume",
            f"{DATABASE / 'changelog'}:/liquibase/changelog:ro",
            *[
                arg
                for key in environment
                if key.startswith("LIQUIBASE_")
                for arg in ("--env", key)
            ],
            "local/deep-copy-liquibase:5.0.4",
            *command,
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        # This helper only accepts local fixture credentials.
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout + result.stderr


@pytest.fixture(scope="session")
def migrated_database():
    url = os.environ.get("MOMENTUM_TEST_ADMIN_URL", "")
    container = os.environ.get("MOMENTUM_TEST_CONTAINER", "")
    address = local_target(url, container)
    metadata = json.loads(
        subprocess.check_output(
            ["docker", "container", "inspect", container],
            text=True,
        )
    )[0]
    if metadata["Config"]["Labels"].get("org.deepcopy.momentum-test") != "true":
        pytest.fail("Refusing an unlabeled database container")
    ports = metadata["NetworkSettings"]["Ports"]["5432/tcp"]
    if ports != [{"HostIp": "127.0.0.1", "HostPort": "55449"}]:
        pytest.fail("Refusing an unexpected PostgreSQL port binding")
    name = "momentum_test_" + uuid4().hex
    owned = {"database": False, "roles": []}
    target = urlunsplit(address._replace(path="/" + name))
    urls = {
        role: urlunsplit(
            address._replace(
                netloc=f"{role}:local-only@127.0.0.1:55449",
                path="/" + name,
            )
        )
        for role in ROLES
    }

    async def setup():
        admin = await asyncpg.connect(url)
        try:
            existing = await admin.fetchval(
                "SELECT count(*) FROM pg_roles WHERE rolname=ANY($1)",
                list(ROLES),
            )
            if existing:
                raise ValueError("Disposable PostgreSQL already contains test roles")
            await admin.execute(f'CREATE DATABASE "{name}"')
            owned["database"] = True
            for role in ROLES:
                await admin.execute(f"CREATE ROLE {role} LOGIN PASSWORD 'local-only'")
                owned["roles"].append(role)
        finally:
            await admin.close()
        owner = await asyncpg.connect(target)
        try:
            await owner.execute((DATABASE / "bootstrap.sql").read_text())
            await owner.execute(f'REVOKE TEMPORARY ON DATABASE "{name}" FROM PUBLIC')
            await owner.execute((DATABASE / "momentum-bootstrap.sql").read_text())
            await owner.execute("CREATE TABLE public.unrelated(value TEXT)")
            await owner.execute("INSERT INTO public.unrelated VALUES ('preserved')")
        finally:
            await owner.close()

    async def cleanup():
        admin = await asyncpg.connect(url)
        try:
            if owned["database"]:
                await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
            for role in reversed(owned["roles"]):
                await admin.execute(f"DROP ROLE {role}")
        finally:
            await admin.close()

    async def verify_default_context():
        owner = await asyncpg.connect(target)
        try:
            assert (
                await owner.fetchval("SELECT count(*) FROM liquibase.databasechangelog")
                == 1
            )
            assert (
                await owner.fetchval(
                    "SELECT count(*) FROM pg_namespace WHERE nspname='momentum'"
                )
                == 0
            )
        finally:
            await owner.close()

    try:
        asyncio.run(setup())
        run_liquibase(urls["database_migrator"], "validate")
        run_liquibase(urls["database_migrator"], "update", context=None)
        asyncio.run(verify_default_context())
        run_liquibase(urls["database_migrator"], "update")
        yield {"admin": target, **urls}
    finally:
        asyncio.run(cleanup())
