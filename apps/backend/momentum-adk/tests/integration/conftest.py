"""Current domain fixtures only, using a labelled disposable PostgreSQL 18 server."""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest

DATABASE = Path(__file__).resolve().parents[5] / "database"
CONTAINER = "momentum-current-test-db"
PORT = 55467
ROLES = (
    "database_migrator",
    "momentum_sessions_writer",
    "momentum_results_writer",
    "momentum_results_reader",
    "market_scanner_writer",  # A foreign domain identity must receive no result grants.
)


@pytest.fixture(scope="session", autouse=True)
def local_transport():
    previous = os.environ.get("PGSSLMODE")
    os.environ["PGSSLMODE"] = "disable"
    yield
    if previous is None:
        os.environ.pop("PGSSLMODE", None)
    else:
        os.environ["PGSSLMODE"] = previous


def local_target(url, container):
    address = urlsplit(url)
    if (
        address.scheme != "postgresql"
        or address.hostname != "127.0.0.1"
        or address.port != PORT
        or address.username != "postgres"
        or address.path != "/postgres"
        or address.query
        or address.fragment
        or container != CONTAINER
    ):
        raise ValueError("Use the labelled disposable localhost PostgreSQL fixture")
    return address


def run_liquibase(url, *command):
    address = urlsplit(url)
    settings = {
        "LIQUIBASE_COMMAND_URL": f"jdbc:postgresql://127.0.0.1:5432{address.path}",
        "LIQUIBASE_COMMAND_USERNAME": address.username,
        "LIQUIBASE_COMMAND_PASSWORD": address.password,
        "LIQUIBASE_COMMAND_CHANGELOG_FILE": "domains/momentum/changelog.yaml",
        "LIQUIBASE_LIQUIBASE_SCHEMA_NAME": "liquibase",
    }
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            f"container:{CONTAINER}",
            "--volume",
            f"{DATABASE}:/liquibase/changelog:ro",
            *[arg for key in settings for arg in ("--env", key)],
            "local/deepcopy-database:5.0.4",
            *command,
        ],
        env={**os.environ, **settings},
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode:
        raise RuntimeError(
            result.stdout + result.stderr
        )  # Local fixture credentials only.
    return result.stdout + result.stderr


def _validate_container():
    metadata = json.loads(
        subprocess.check_output(["docker", "inspect", CONTAINER], text=True)
    )[0]
    if metadata["Config"]["Labels"].get("org.deepcopy.momentum-test") != "true":
        pytest.fail("Refusing an unlabelled PostgreSQL container")
    if metadata["HostConfig"]["PortBindings"].get("5432/tcp") != [
        {"HostIp": "127.0.0.1", "HostPort": str(PORT)}
    ]:
        pytest.fail("Refusing an unexpected PostgreSQL binding")
    if not metadata.get("State", {}).get("Running") or metadata.get(
        "NetworkSettings", {}
    ).get("Ports", {}).get("5432/tcp") != [
        {"HostIp": "127.0.0.1", "HostPort": str(PORT)}
    ]:
        pytest.fail("Refusing a stopped or inactive PostgreSQL container")


async def _seed_upgrade(url):
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(
            "INSERT INTO _sessions.sessions VALUES "
            "('upgrade','test','preserved','{}',NOW(),NOW())"
        )
        return await connection.fetch(
            "SELECT id, md5sum FROM liquibase.databasechangelog ORDER BY id"
        )
    finally:
        await connection.close()


async def _verify_upgrade(url, baseline_history):
    connection = await asyncpg.connect(url)
    try:
        assert (
            await connection.fetchval(
                "SELECT count(*) FROM _sessions.sessions WHERE app_name='upgrade'"
            )
            == 1
        )
        for row in baseline_history:
            assert (
                await connection.fetchval(
                    "SELECT md5sum FROM liquibase.databasechangelog WHERE id=$1",
                    row["id"],
                )
                == row["md5sum"]
            )
        await connection.execute(
            "DELETE FROM _sessions.sessions WHERE app_name='upgrade'"
        )
    finally:
        await connection.close()


@pytest.fixture(scope="session")
def domain_database(local_transport):
    address = local_target(
        os.environ.get("MOMENTUM_TEST_ADMIN_URL", ""),
        os.environ.get("MOMENTUM_TEST_CONTAINER", ""),
    )
    _validate_container()
    urls = {"admin": urlunsplit(address._replace(path="/momentum"))}
    for key, role in [
        ("migrator", ROLES[0]),
        ("sessions_runtime", ROLES[1]),
        ("results_runtime", ROLES[2]),
    ]:
        urls[key] = urlunsplit(
            address._replace(
                netloc=f"{role}:local-only@127.0.0.1:{PORT}", path="/momentum"
            )
        )
    owned_roles = []
    owned_database = False

    async def setup():
        nonlocal owned_database
        admin = await asyncpg.connect(urlunsplit(address))
        try:
            if await admin.fetchval(
                "SELECT EXISTS(SELECT FROM pg_roles WHERE rolname=ANY($1))", list(ROLES)
            ):
                raise ValueError("Disposable server already contains test roles")
            for role in ROLES:
                await admin.execute(f"CREATE ROLE {role} LOGIN PASSWORD 'local-only'")
                owned_roles.append(role)
            await admin.execute(
                "REVOKE CONNECT ON DATABASE postgres, template1 FROM PUBLIC"
            )
            await admin.execute("CREATE DATABASE momentum")
            owned_database = True
        finally:
            await admin.close()
        for key, path in [
            ("admin", "domains/momentum/bootstrap.sql"),
            ("migrator", "operations/prepare.sql"),
        ]:
            connection = await asyncpg.connect(urls[key])
            try:
                await connection.execute((DATABASE / path).read_text())
            finally:
                await connection.close()

    async def cleanup():
        admin = await asyncpg.connect(urlunsplit(address))
        try:
            if owned_database:
                await admin.execute("DROP DATABASE momentum WITH (FORCE)")
            for role in reversed(owned_roles):
                await admin.execute(f"DROP ROLE {role}")
        finally:
            await admin.close()

    try:
        asyncio.run(setup())
        run_liquibase(urls["migrator"], "validate")
        run_liquibase(urls["migrator"], "update-to-tag", "--tag=aiven-20261023")

        baseline_history = asyncio.run(_seed_upgrade(urls["admin"]))
        run_liquibase(urls["migrator"], "update")
        run_liquibase(urls["migrator"], "update")

        asyncio.run(_verify_upgrade(urls["admin"], baseline_history))
        yield urls
    finally:
        asyncio.run(cleanup())
