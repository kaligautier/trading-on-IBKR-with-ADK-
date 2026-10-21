"""Repeat/rollback Momentum without changing Scanner data or history."""

import asyncpg
from conftest import run_liquibase


async def test_migrations_repeat_and_rollback_preserve_scanner(migrated_database):
    admin = await asyncpg.connect(migrated_database["admin"])
    migrator_url = migrated_database["database_migrator"]
    try:
        checksum = await admin.fetchval(
            "SELECT md5sum FROM liquibase.databasechangelog "
            "WHERE id='market-scanner-001'"
        )
        await admin.execute(
            "INSERT INTO market_scanner.market_scans "
            "(id, scan_date, session_id, regime, summary, created_at) VALUES "
            "('d33d8f79-6a90-4aad-a7d7-d990ed341c47', CURRENT_DATE, "
            "'migration-test', 'neutral', 'local fixture', NOW())"
        )
        scanner_before = await admin.fetchval(
            "SELECT jsonb_agg(to_jsonb(s)) FROM market_scanner.market_scans s"
        )
        run_liquibase(migrator_url, "update")
        assert (
            await admin.fetchval("SELECT count(*) FROM liquibase.databasechangelog")
            == 3
        )
        run_liquibase(migrator_url, "rollback-count", "--count=2")
        assert (
            await admin.fetchval(
                "SELECT count(*) FROM pg_namespace WHERE nspname='momentum'"
            )
            == 0
        )
        assert (
            await admin.fetchval(
                "SELECT jsonb_agg(to_jsonb(s)) FROM market_scanner.market_scans s"
            )
            == scanner_before
        )
        assert (
            await admin.fetchval(
                "SELECT md5sum FROM liquibase.databasechangelog "
                "WHERE id='market-scanner-001'"
            )
            == checksum
        )
        assert await admin.fetchval("SELECT value FROM public.unrelated") == "preserved"
    finally:
        run_liquibase(migrator_url, "update")
        await admin.close()
