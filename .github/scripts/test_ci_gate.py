"""Regression coverage for component selection and the required merge gate."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ci_result import verify
from ci_scope import COMPONENTS, changed_paths, select


def results(paths=(), *, full=False):
    selected = select(list(paths), full=full)
    return {
        "scope": {
            "result": "success",
            "outputs": {"selected": json.dumps(selected)},
        },
        **{
            name: {
                "result": "success" if selected[name] else "skipped",
                "outputs": {
                    "jobs": json.dumps(
                        {job: {"result": "success"} for job in component["jobs"]}
                    )
                }
                if selected[name]
                else {},
            }
            for name, component in COMPONENTS.items()
        },
    }


class ScopeTests(unittest.TestCase):
    def test_documentation_only_runs_no_component(self):
        self.assertFalse(any(select(["README.md", "docs/guide.md"]).values()))

    def test_frontend_runs_its_build_without_unrelated_apps(self):
        selected = select(["apps/frontend/app/page.tsx"])
        self.assertEqual(
            [key for key, value in selected.items() if value], ["frontend"]
        )

    def test_shared_writer_contract_selects_reader_and_writer(self):
        selected = select(["apps/backend/market-scanner-adk/src/app/models/report.py"])
        self.assertTrue(selected["scanner"])
        self.assertTrue(selected["scanner_reader"])

    def test_database_changes_select_both_readers_and_momentum(self):
        selected = select(["database/domains/momentum/changelog.yaml"])
        for name in ("momentum", "momentum_api", "scanner_reader"):
            self.assertTrue(selected[name])

    def test_each_workflow_selects_itself(self):
        for name, component in COMPONENTS.items():
            with self.subTest(name=name):
                self.assertTrue(
                    select([".github/workflows/" + component["workflow"]])[name]
                )

    def test_gate_changes_and_dispatch_select_every_component(self):
        for path in (
            ".github/workflows/ci.yml",
            ".github/ci-components.json",
            ".github/scripts/ci_result.py",
        ):
            self.assertTrue(all(select([path]).values()))
        self.assertTrue(all(select([], full=True).values()))

    def test_diff_keeps_both_paths_of_a_cross_component_rename(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return subprocess.check_output(
                    ["git", *args], cwd=root, text=True
                ).strip()

            git("init", "-q")
            git("config", "user.email", "ci-test@example.invalid")
            git("config", "user.name", "CI test")
            old = root / "apps/frontend/old.txt"
            new = root / "apps/backend/momentum-adk/new.txt"
            old.parent.mkdir(parents=True)
            new.parent.mkdir(parents=True)
            old.write_text("unchanged contents\n")
            git("add", ".")
            git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            old.rename(new)
            git("add", ".")
            git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "rename")
            with patch("ci_scope.ROOT", root):
                paths = changed_paths(base, git("rev-parse", "HEAD"))
            self.assertEqual(
                set(paths), {str(old.relative_to(root)), str(new.relative_to(root))}
            )
            selected = select(paths)
            self.assertTrue(selected["frontend"] and selected["momentum"])


class ResultTests(unittest.TestCase):
    def test_documentation_and_successful_selected_components_pass(self):
        verify(results())
        verify(results(["apps/frontend/app/page.tsx"]))
        verify(results(full=True))

    def test_failed_cancelled_and_skipped_selected_workflows_fail(self):
        for status in ("failure", "cancelled", "skipped", "neutral", ""):
            with self.subTest(status=status):
                needs = results(full=True)
                needs["frontend"]["result"] = status
                with self.assertRaises(ValueError):
                    verify(needs)

    def test_skipped_or_failed_child_job_cannot_hide_behind_workflow_success(self):
        for status in ("skipped", "failure", "cancelled"):
            needs = results(full=True)
            jobs = json.loads(needs["frontend"]["outputs"]["jobs"])
            jobs["container"]["result"] = status
            needs["frontend"]["outputs"]["jobs"] = json.dumps(jobs)
            with self.assertRaises(ValueError):
                verify(needs)

    def test_missing_workflow_or_job_fails(self):
        needs = results(full=True)
        del needs["frontend"]
        with self.assertRaises(ValueError):
            verify(needs)
        needs = results(full=True)
        needs["frontend"]["outputs"]["jobs"] = "{}"
        with self.assertRaises(ValueError):
            verify(needs)

    def test_missing_or_malformed_outputs_fail(self):
        for output in ({}, {"jobs": ""}, {"jobs": "not-json"}):
            needs = results(full=True)
            needs["frontend"]["outputs"] = output
            with self.assertRaises((ValueError, KeyError)):
                verify(needs)

    def test_scope_failures_and_incomplete_selection_fail(self):
        for status in ("failure", "skipped", "cancelled"):
            needs = results()
            needs["scope"]["result"] = status
            with self.assertRaises(ValueError):
                verify(needs)
        for selection in ({}, {**select([]), "frontend": "false"}):
            needs = results()
            needs["scope"]["outputs"]["selected"] = json.dumps(selection)
            with self.assertRaises(ValueError):
                verify(needs)

    def test_unexpected_execution_is_rejected(self):
        needs = results()
        needs["frontend"]["result"] = "success"
        with self.assertRaises(ValueError):
            verify(needs)


if __name__ == "__main__":
    unittest.main()
