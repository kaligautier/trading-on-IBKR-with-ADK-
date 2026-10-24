"""Release verification follows migrations and rejects drift or missing history."""

import argparse
import json
import shutil

import asyncpg
import pytest

from test_baseline import ROOT, management, url
from test_ratio_rollback import harness


@pytest.fixture(scope="module")
def current_databases(domain_databases):
    db = harness()
    for domain in db.DOMAINS:
        db.migrate(domain)
        db.migrate(domain)
    yield db
    db.reset()


@pytest.mark.parametrize("domain", ["market_scanner", "momentum"])
async def test_current_manifest_matches_clean_replay(
    current_databases, domain, monkeypatch
):
    module = management()
    from operations.current import capture_current

    connection = await asyncpg.connect(url(domain))
    try:
        assert await capture_current(connection, ROOT, domain) == json.loads(
            (ROOT / "domains" / domain / "current.json").read_text()
        )
    finally:
        await connection.close()
    monkeypatch.setenv("DATABASE_URL", url(domain))
    await module.execute(
        argparse.Namespace(
            action="verify",
            domain=domain,
            url_file=None,
            ca_file=None,
        )
    )


async def test_baseline_verifier_remains_distinct(current_databases, monkeypatch):
    module = management()
    monkeypatch.setenv("DATABASE_URL", url("momentum"))
    with pytest.raises(ValueError, match="baseline"):
        await module.execute(
            argparse.Namespace(
                action="verify-baseline",
                domain="momentum",
                url_file=None,
                ca_file=None,
            )
        )


@pytest.mark.parametrize(
    "role,column,privilege,was_allowed,mutation,restore",
    [
        (
            "momentum_results_reader",
            "decision",
            "SELECT",
            False,
            "GRANT SELECT (decision) ON _analysis.trading_memory TO momentum_results_reader",
            "REVOKE SELECT (decision) ON _analysis.trading_memory FROM momentum_results_reader",
        ),
        (
            "momentum_results_writer",
            "reflection",
            "UPDATE",
            True,
            "REVOKE UPDATE (reflection) ON _analysis.trading_memory FROM momentum_results_writer",
            "GRANT UPDATE (reflection) ON _analysis.trading_memory TO momentum_results_writer",
        ),
    ],
    ids=["private-column-exposed", "required-writer-grant-removed"],
)
async def test_verify_rejects_column_privilege_drift(
    current_databases,
    monkeypatch,
    role,
    column,
    privilege,
    was_allowed,
    mutation,
    restore,
):
    module = management()
    monkeypatch.setenv("DATABASE_URL", url("momentum"))
    args = argparse.Namespace(
        action="verify", domain="momentum", url_file=None, ca_file=None
    )
    await module.execute(args)
    connection = await asyncpg.connect(url("momentum"))
    try:
        check = "SELECT has_column_privilege($1, '_analysis.trading_memory', $2, $3)"
        assert await connection.fetchval(check, role, column, privilege) == was_allowed
        await connection.execute(mutation)
        assert await connection.fetchval(check, role, column, privilege) != was_allowed
    finally:
        await connection.close()
    try:
        with pytest.raises(ValueError, match="Schema differs"):
            await module.execute(args)
    finally:
        connection = await asyncpg.connect(url("momentum"))
        try:
            await connection.execute(restore)
        finally:
            await connection.close()
    await module.execute(args)


@pytest.mark.parametrize(
    "mutation", ["column", "grant", "missing", "checksum", "null_checksum"]
)
async def test_current_verification_rejects_drift(current_databases, mutation):
    module = management()
    connection = await asyncpg.connect(url("momentum"))
    transaction = connection.transaction(isolation="repeatable_read")
    await transaction.start()
    try:
        commands = {
            "column": "ALTER TABLE _analysis.trading_memory ADD COLUMN unexpected text",
            "grant": "GRANT SELECT ON _analysis.trading_memory TO momentum_results_reader",
            "missing": "DELETE FROM liquibase.databasechangelog WHERE id='momentum-trader-ratio-text-001'",
            "checksum": "UPDATE liquibase.databasechangelog SET md5sum='9:invalid' WHERE id='momentum-trader-ratio-text-001'",
            "null_checksum": "UPDATE liquibase.databasechangelog SET md5sum=NULL WHERE id='momentum-trader-ratio-text-001'",
        }
        await connection.execute(commands[mutation])
        with pytest.raises(ValueError, match="differs|missing"):
            await module.require_current(connection, ROOT, "momentum")
    finally:
        await transaction.rollback()
        await connection.close()


async def test_adopted_baseline_and_retained_legacy_history_are_accepted(
    current_databases,
):
    module = management()
    connection = await asyncpg.connect(url("momentum"))
    transaction = connection.transaction(isolation="repeatable_read")
    await transaction.start()
    try:
        await connection.execute("""
UPDATE liquibase.databasechangelog SET exectype='MARK_RAN' WHERE author='deepcopy'
 AND id LIKE 'momentum-aiven-%';
INSERT INTO liquibase.databasechangelog
 (id,author,filename,dateexecuted,orderexecuted,exectype,md5sum)
VALUES ('retained-legacy','legacy','legacy.sql',NOW(),0,'EXECUTED',NULL);
""")
        await module.require_current(connection, ROOT, "momentum")
    finally:
        await transaction.rollback()
        await connection.close()


async def test_next_migration_requires_refreshed_manifest(
    current_databases, mounted_changelog
):
    tmp_path = mounted_changelog
    module = management()
    from operations.current import capture_current

    shutil.copytree(ROOT / "domains", tmp_path / "domains")
    domain = tmp_path / "domains/market_scanner"
    baseline = (domain / "baseline.sql").read_bytes()
    (domain / "next.sql").write_text(
        "--liquibase formatted sql\n--changeset test:next-column\n"
        "ALTER TABLE _analysis.market_scans ADD COLUMN review_note text;\n"
    )
    with (domain / "changelog.yaml").open("a") as stream:
        stream.write(
            "  - include:\n      file: next.sql\n      relativeToChangelogFile: true\n"
        )
    db = harness()
    db.ROOT = tmp_path
    db.migrate("market_scanner")
    connection = await asyncpg.connect(url("market_scanner"))
    try:
        with pytest.raises(ValueError, match="stale"):
            await module.require_current(connection, tmp_path, "market_scanner")
        state = await capture_current(connection, tmp_path, "market_scanner")
        (domain / "current.json").write_text(json.dumps(state))
        await module.require_current(connection, tmp_path, "market_scanner")
        assert (domain / "baseline.sql").read_bytes() == baseline
    finally:
        await connection.execute(
            "ALTER TABLE _analysis.market_scans DROP COLUMN review_note"
        )
        await connection.execute(
            "DELETE FROM liquibase.databasechangelog WHERE id='next-column'"
        )
        await connection.close()
