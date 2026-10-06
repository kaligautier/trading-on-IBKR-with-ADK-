"""Real permissions, migration ownership and concurrency on local PostgreSQL."""

import asyncio
import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import TimeoutError

from app.config.settings import settings
from app.services import database
from app.services.market_scan_persistence import MarketScanPersistence
from test.unit.services.test_market_scan_persistence import _regime

ROOT = Path(__file__).resolve().parents[3]
DATABASE_ROOT = ROOT.parents[2] / "database"
ROLES = ("market_scanner_writer", "market_scanner_reader", "database_migrator")


@pytest.fixture
async def shared_database(monkeypatch):
    url = os.getenv("MARKET_SHARED_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set MARKET_SHARED_TEST_DATABASE_URL to disposable local PostgreSQL"
        )
    address = make_url(url)
    if address.host not in {"127.0.0.1", "localhost"}:
        pytest.fail("Shared database tests require a local PostgreSQL host")
    admin = await asyncpg.connect(url)
    existing = await admin.fetchval(
        "SELECT count(*) FROM pg_roles WHERE rolname = ANY($1)", list(ROLES)
    )
    if existing:
        await admin.close()
        pytest.fail("Use a disposable server: test roles already exist")
    name = f"shared_test_{uuid4().hex}"
    await admin.execute(f'CREATE DATABASE "{name}"')
    target = address.set(database=name)
    owner = await asyncpg.connect(target.render_as_string(hide_password=False))
    connections = []
    try:
        for role in ROLES:
            await admin.execute(f"CREATE ROLE \"{role}\" LOGIN PASSWORD 'local-only'")
        await owner.execute((DATABASE_ROOT / "bootstrap.sql").read_text())
        # A separate domain and public data must remain unaffected.
        await owner.execute("CREATE TABLE public.unrelated (value TEXT)")
        await owner.execute("INSERT INTO public.unrelated VALUES ('preserved')")
        urls = {
            role: target.set(username=role, password="local-only").render_as_string(
                hide_password=False
            )
            for role in ROLES
        }
        reader = await asyncpg.connect(urls[ROLES[1]])
        connections.append(reader)
        monkeypatch.setattr(settings, "DATABASE_URL", urls[ROLES[0]])
        monkeypatch.setattr(settings, "DATABASE_SCHEMA", "market_scanner")
        monkeypatch.setattr(settings, "DATABASE_POOL_SIZE", 1)
        monkeypatch.setattr(settings, "DATABASE_POOL_TIMEOUT", 0.1)
        await database.close_database()
        yield owner, owner, reader, urls
    finally:
        await database.close_database()
        for connection in connections:
            await connection.close()
        await owner.close()
        await admin.execute(f'DROP DATABASE "{name}"')
        for role in ROLES:
            await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        await admin.close()


async def should_migrate_once_and_enforce_writer_reader_permissions(shared_database):
    owner, migrator, reader, urls = shared_database
    await run_liquibase(urls[ROLES[2]])
    await run_liquibase(urls[ROLES[2]])
    assert (
        await migrator.fetchval("SELECT count(*) FROM liquibase.databasechangelog") == 1
    )
    await MarketScanPersistence().save(_regime(), "shared-database")
    assert await reader.fetchval("SELECT count(*) FROM market_scans") == 1
    assert await reader.fetchval("SELECT report->>'summary' FROM market_scans")
    assert await owner.fetchval("SELECT value FROM public.unrelated") == "preserved"

    for query in (
        "DELETE FROM market_scans",
        "INSERT INTO market_scans SELECT * FROM market_scans",
        "CREATE TABLE market_scanner.forbidden (id INT)",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await reader.execute(query)
    writer = await asyncpg.connect(urls[ROLES[0]])
    try:
        for query in (
            "SELECT * FROM market_scans",
            "SELECT * FROM public.unrelated",
            "DELETE FROM market_scans",
            "CREATE TABLE market_scanner.forbidden (id INT)",
            "SELECT * FROM liquibase.databasechangelog",
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await writer.execute(query)

    finally:
        await writer.close()


async def should_serialize_concurrent_saves_and_timeout_without_overflow(
    shared_database,
):
    _, _, reader, urls = shared_database
    await run_liquibase(urls[ROLES[2]])
    engine = database.get_engine()
    async with engine.connect() as held:
        pid = await held.scalar(text("SELECT pg_backend_pid()"))
        with pytest.raises(TimeoutError):
            await MarketScanPersistence().save(_regime(), "pool-full")
    assert await reader.fetchval("SELECT count(*) FROM market_scans") == 0
    await asyncio.gather(
        *(MarketScanPersistence().save(_regime(), f"parallel-{i}") for i in range(5))
    )
    assert await reader.fetchval("SELECT count(*) FROM market_scans") == 5
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT pg_backend_pid()")) == pid
    assert engine.pool.size() == 1
    assert engine.pool.overflow() == 0


@pytest.fixture
def mounted_tmp_path():
    # Colima mounts the workspace, but not macOS /var/folders pytest directories.
    with TemporaryDirectory(dir=ROOT / ".pytest_cache") as directory:
        yield Path(directory)


async def should_rollback_a_failed_migration_and_detect_changed_history(
    shared_database, mounted_tmp_path
):
    owner, migrator, _, urls = shared_database
    await run_liquibase(urls[ROLES[2]])
    changelog = mounted_tmp_path / "changelog"
    shutil.copytree(DATABASE_ROOT / "changelog", changelog)
    master = changelog / "db.changelog-master.yaml"
    master.write_text(
        master.read_text()
        + "  - include:\n      file: broken.sql\n      relativeToChangelogFile: true\n"
    )
    broken = changelog / "broken.sql"
    broken.write_text(
        "--liquibase formatted sql\n--changeset test:broken\n"
        "CREATE TABLE market_scanner.partial (id INT); SELECT 1/0;\n"
    )
    with pytest.raises(RuntimeError, match="division by zero"):
        await run_liquibase(urls[ROLES[2]], changelog=changelog)
    assert await owner.fetchval("SELECT to_regclass('market_scanner.partial')") is None
    assert (
        await migrator.fetchval("SELECT count(*) FROM liquibase.databasechangelog") == 1
    )
    initial = changelog / "market-scanner/001-initial.sql"
    initial.write_text(
        initial.read_text().replace("summary TEXT", "summary VARCHAR(10)")
    )
    with pytest.raises(RuntimeError, match="check sum|checksum|Check Sum"):
        await run_liquibase(urls[ROLES[2]], changelog=changelog)


async def should_add_and_rollback_another_domain_from_the_same_root(
    shared_database, mounted_tmp_path
):
    owner, _, reader, urls = shared_database
    changelog = mounted_tmp_path / "changelog"
    shutil.copytree(DATABASE_ROOT / "changelog", changelog)
    master = changelog / "db.changelog-master.yaml"
    master.write_text(
        master.read_text() + "  - include:\n      file: other-domain.sql\n"
        "      relativeToChangelogFile: true\n"
    )
    (changelog / "other-domain.sql").write_text(
        "--liquibase formatted sql\n--changeset test:other-domain\n"
        "CREATE SCHEMA other_domain;\n"
        "CREATE TABLE other_domain.example (id INT);\n"
        "--rollback DROP TABLE other_domain.example;\n"
        "--rollback DROP SCHEMA other_domain;\n"
    )
    await run_liquibase(urls[ROLES[2]], changelog=changelog)
    assert await owner.fetchval("SELECT count(*) FROM liquibase.databasechangelog") == 2
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await reader.execute("SELECT * FROM other_domain.example")
    await run_liquibase(
        urls[ROLES[2]], command=("rollback-count", "--count=1"), changelog=changelog
    )
    assert await owner.fetchval("SELECT to_regclass('other_domain.example')") is None
    assert await reader.fetchval("SELECT count(*) FROM market_scans") == 0
    assert await owner.fetchval("SELECT count(*) FROM liquibase.databasechangelog") == 1


async def run_liquibase(url, command="update", changelog=None):
    """Run actual Liquibase against the explicitly named disposable test container."""
    container = os.getenv("MARKET_SHARED_TEST_CONTAINER")
    if not container:
        pytest.fail(
            "Set MARKET_SHARED_TEST_CONTAINER to the disposable PostgreSQL container"
        )
    address = make_url(url)
    environment = {
        **os.environ,
        "LIQUIBASE_COMMAND_URL": f"jdbc:postgresql://127.0.0.1:5432/{address.database}",
        "LIQUIBASE_COMMAND_USERNAME": address.username,
        "LIQUIBASE_COMMAND_PASSWORD": address.password,
        "LIQUIBASE_COMMAND_CHANGELOG_FILE": "db.changelog-master.yaml",
        "LIQUIBASE_LIQUIBASE_SCHEMA_NAME": "liquibase",
    }
    process = await asyncio.create_subprocess_exec(
        "docker",
        "run",
        "--rm",
        "--network",
        f"container:{container}",
        "-v",
        f"{changelog or DATABASE_ROOT / 'changelog'}:/liquibase/changelog:ro",
        *[
            arg
            for key in environment
            if key.startswith("LIQUIBASE_")
            for arg in ("-e", key)
        ],
        "local/deep-copy-liquibase:5.0.4",
        *([command] if isinstance(command, str) else command),
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    output, _ = await process.communicate()
    if process.returncode:
        raise RuntimeError(output.decode())
    return output.decode()
