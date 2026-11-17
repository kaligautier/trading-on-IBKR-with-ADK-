"""The protected check must be emitted even for a documentation-only PR."""

from pathlib import Path

import yaml


def test_database_check_always_runs_and_propagates_failures():
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.load(
        (root / ".github/workflows/domain-database.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    assert workflow["on"]["pull_request"] == ""
    assert workflow["on"]["push"]["branches"] == ["main"]
    job = workflow["jobs"]["local-postgres"]
    assert job["name"] == "Database migrations"
    assert "if" not in job and "continue-on-error" not in job
    assert all("continue-on-error" not in step for step in job["steps"])
    assert job["steps"][-1]["run"] == "python3 database/testing/rehearse.py"
