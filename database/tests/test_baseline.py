"""Prove reconstruction, drift rejection and non-destructive baseline adoption."""

import argparse
import importlib.util
import json
from pathlib import Path

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.usefixtures("domain_databases")


def management():
    spec = importlib.util.spec_from_file_location(
        "domain_management", ROOT / "manage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def url(domain, role="database_migrator"):
    return f"postgresql://{role}:domain-test-only@127.0.0.1:55471/{domain}"


@pytest.mark.parametrize("domain", ["market_scanner", "momentum"])
async def test_fresh_baseline_matches_live_aiven_structure_and_grants(domain):
    module = management()
    connection = await asyncpg.connect(url(domain))
    try:
        expected = json.loads((ROOT / "domains.json").read_text())[domain][
            "fingerprint"
        ]
        module.require_baseline(await module.snapshot(connection), expected)
        assert (
            await connection.fetchval(
                "SELECT value FROM _sessions.adk_internal_metadata WHERE key='schema_version'"
            )
            == "1"
        )
        assert await connection.fetchval("SHOW server_version_num") >= "180000"
    finally:
        await connection.close()


async def test_adoption_marks_only_baseline_and_preserves_existing_rows(monkeypatch):
    module = management()
    admin = await asyncpg.connect(url("momentum", "postgres"))
    original = await module.snapshot(admin)
    try:
        await admin.execute(
            "INSERT INTO _sessions.sessions VALUES ('adoption','test','preserved','{}',NOW(),NOW())"
        )
        await admin.execute(
            "DELETE FROM liquibase.databasechangelog WHERE tag IS NOT NULL"
        )
        await admin.execute(
            "UPDATE liquibase.databasechangelog SET id='previous-baseline',author='imported',filename='previous-entrypoint.sql',md5sum=NULL"
        )
        monkeypatch.setenv("DATABASE_URL", url("momentum"))
        await module.execute(
            argparse.Namespace(
                action="adopt",
                domain="momentum",
                url_file=None,
                ca_file=None,
            )
        )
        assert await module.snapshot(admin) == original
        assert (
            await admin.fetchval(
                "SELECT count(*) FROM _sessions.sessions WHERE id='preserved'"
            )
            == 1
        )
        assert (
            await admin.fetchval(
                "SELECT count(*) FROM liquibase.databasechangelog WHERE id='previous-baseline'"
            )
            == 1
        )
        ids = {
            row["id"]
            for row in await admin.fetch("SELECT id FROM liquibase.databasechangelog")
        }
        assert ids == {
            "previous-baseline",
            "momentum-aiven-20261023",
            "momentum-aiven-20261023-tag",
        }
        assert not await admin.fetchval(
            "SELECT attnotnull FROM pg_attribute WHERE attrelid='_analysis.sentiment_items'::regclass AND attname='sentiment_score'"
        )
    finally:
        await admin.execute("DELETE FROM _sessions.sessions WHERE id='preserved'")
        await admin.execute(
            "DELETE FROM liquibase.databasechangelog WHERE id='previous-baseline'"
        )
        await admin.close()


async def test_drift_prevents_adoption_without_changing_history(monkeypatch):
    module = management()
    admin = await asyncpg.connect(url("market_scanner", "postgres"))
    before = await admin.fetch("SELECT * FROM liquibase.databasechangelog ORDER BY id")
    try:
        await admin.execute(
            "ALTER TABLE _analysis.market_scans ADD COLUMN unexpected text"
        )
        monkeypatch.setenv("DATABASE_URL", url("market_scanner"))
        with pytest.raises(ValueError, match="differs"):
            await module.execute(
                argparse.Namespace(
                    action="adopt",
                    domain="market_scanner",
                    url_file=None,
                    ca_file=None,
                )
            )
        assert (
            await admin.fetch("SELECT * FROM liquibase.databasechangelog ORDER BY id")
            == before
        )
    finally:
        await admin.execute("ALTER TABLE _analysis.market_scans DROP COLUMN unexpected")
        await admin.close()


@pytest.mark.parametrize(
    "mutation", ["limit", "cross_domain", "nologin", "postgres", "new_database"]
)
async def test_runtime_privilege_drift_prevents_adoption(monkeypatch, mutation):
    module = management()
    admin = await asyncpg.connect(url("market_scanner", "postgres"))
    before = await admin.fetch("SELECT * FROM liquibase.databasechangelog ORDER BY id")
    try:
        if mutation == "limit":
            await admin.execute("ALTER ROLE market_scanner_writer CONNECTION LIMIT 9")
        elif mutation == "nologin":
            await admin.execute("ALTER ROLE market_scanner_writer NOLOGIN")
        elif mutation == "new_database":
            await admin.execute("CREATE DATABASE isolation_probe")
        else:
            target = "postgres" if mutation == "postgres" else "momentum"
            await admin.execute(
                f"GRANT CONNECT ON DATABASE {target} TO market_scanner_writer"
            )
        monkeypatch.setenv("DATABASE_URL", url("market_scanner"))
        with pytest.raises(ValueError, match="access policy"):
            await module.execute(
                argparse.Namespace(
                    action="adopt",
                    domain="market_scanner",
                    url_file=None,
                    ca_file=None,
                )
            )
        assert (
            await admin.fetch("SELECT * FROM liquibase.databasechangelog ORDER BY id")
            == before
        )
    finally:
        await admin.execute("ALTER ROLE market_scanner_writer LOGIN CONNECTION LIMIT 4")
        if mutation == "new_database":
            await admin.execute("DROP DATABASE IF EXISTS isolation_probe")
        await admin.execute(
            "REVOKE CONNECT ON DATABASE momentum, postgres FROM market_scanner_writer"
        )
        await admin.close()
