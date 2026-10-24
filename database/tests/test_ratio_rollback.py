"""A legacy changeset must not narrow the schema captured by the new baseline."""

import importlib.util
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
RATIO = Path("changelog/momentum-unified/trader-ratio-text.sql")


def harness():
    spec = importlib.util.spec_from_file_location(
        "rollback_domains", ROOT / "testing/local_domains.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.usefixtures("domain_databases")
def test_legacy_checksum_and_long_values_survive_rollback(mounted_changelog):
    tmp_path = mounted_changelog
    db = harness()
    # A private changelog copy stops before the unrelated, forward-only memory
    # migration. Keep the exact logical identity used by deployed Liquibase.
    shutil.copytree(ROOT / "domains", tmp_path / "domains")
    shutil.copytree(ROOT / "changelog", tmp_path / "changelog")
    changelog = tmp_path / "domains/momentum/changelog.yaml"
    changelog.write_text(
        changelog.read_text().split("  - include:\n      file: migrations/")[0]
    )
    fixed = (tmp_path / RATIO).read_text()
    original = fixed.replace(
        "--rollback SELECT 1;\n",
        (
            "--rollback ALTER TABLE _analysis.trader_proposals ALTER COLUMN "
            "risk_reward_ratio TYPE VARCHAR(20);\n"
        ),
    )
    (tmp_path / RATIO).write_text(original)
    db.ROOT = tmp_path
    try:
        db.migrate("momentum")
        history = (
            "SELECT id,filename,md5sum FROM liquibase.databasechangelog ORDER BY id"
        )
        before = db.sql("momentum", history)
        # Real constraints and real long values, not a truncated rollback fixture.
        db.sql(
            "momentum",
            """
INSERT INTO _analysis.analysis_results
 (session_id,invocation_id,user_id,id,ticker,analysis_date,llm_provider,
  deep_think_llm,quick_think_llm,created_at)
VALUES ('rollback','rollback','rollback','00000000-0000-0000-0000-000000000001',
 'TEST',CURRENT_DATE,'fixture','fixture','fixture',NOW());
INSERT INTO _analysis.trader_proposals
 (id,result_id,ticker,analysis_date,action,reasoning,risk_reward_ratio)
VALUES ('00000000-0000-0000-0000-000000000002',
 '00000000-0000-0000-0000-000000000001','TEST',CURRENT_DATE,'HOLD','fixture',
 'An explanatory risk reward ratio longer than twenty characters');
""",
        )
        (tmp_path / RATIO).write_text(fixed)
        db.migrate("momentum", "validate")
        db.migrate("momentum")
        assert db.sql("momentum", history) == before
        db.migrate("momentum", ["rollback-count", "--count=1"])
        assert "text" in db.sql(
            "momentum",
            """
SELECT format_type(atttypid,atttypmod) FROM pg_attribute
WHERE attrelid='_analysis.trader_proposals'::regclass AND attname='risk_reward_ratio';
""",
        )
        assert "longer than twenty characters" in db.sql(
            "momentum", "SELECT risk_reward_ratio FROM _analysis.trader_proposals"
        )
        db.migrate("momentum")
        assert db.sql("momentum", history) == before
    finally:
        # Other foundation tests intentionally exercise the baseline, not HEAD.
        db.ROOT = ROOT
        db.reset()
