import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from check_pr_components import changed_components


class ComponentScopeTests(unittest.TestCase):
    def check(self, entries, *, count=None, head="current", pages=None):
        report = {
            "head": {"sha": head},
            "changed_files": len(entries) if count is None else count,
        }
        return changed_components(
            report, [entries] if pages is None else pages, "current"
        )

    def test_one_backend_with_tests_lockfile_and_shared_changes(self):
        paths = [
            "apps/backend/market-scanner-api/src/app/main.py",
            "apps/backend/market-scanner-api/src/test/test_api.py",
            "apps/backend/market-scanner-api/uv.lock",
            ".github/workflows/scanner-reader.yml",
            "database/changelog/schema.sql",
            "infra/reader/main.tf",
            "docs/api.md",
        ]
        self.assertEqual(
            self.check([{"filename": path} for path in paths]),
            ["apps/backend/market-scanner-api"],
        )

    def test_two_backends_are_distinct_components(self):
        files = [{"filename": f"apps/backend/{name}/main.py"} for name in ("a", "b")]
        self.assertEqual(self.check(files), ["apps/backend/a", "apps/backend/b"])

    def test_frontend_and_backend_are_distinct(self):
        files = [
            {"filename": path}
            for path in ("apps/frontend/src/app/page.tsx", "apps/backend/a/main.py")
        ]
        self.assertEqual(self.check(files), ["apps/backend/a", "apps/frontend"])

    def test_shared_only_and_empty_prs(self):
        self.assertEqual(self.check([{"filename": "CONTRIBUTING.md"}]), [])
        self.assertEqual(self.check([]), [])

    def test_future_components_are_detected_without_configuration(self):
        self.assertEqual(
            self.check([{"filename": "apps/backend/new-service/Dockerfile"}]),
            ["apps/backend/new-service"],
        )
        self.assertEqual(
            self.check([{"filename": "apps/new-app/package.json"}]), ["apps/new-app"]
        )

    def test_renames_count_both_components(self):
        self.assertEqual(
            self.check(
                [
                    {
                        "filename": "apps/backend/b/main.py",
                        "status": "renamed",
                        "previous_filename": "apps/backend/a/main.py",
                    }
                ]
            ),
            ["apps/backend/a", "apps/backend/b"],
        )

    def test_rename_outside_apps_still_counts_old_component(self):
        self.assertEqual(
            self.check(
                [
                    {
                        "filename": "docs/example.py",
                        "status": "renamed",
                        "previous_filename": "apps/backend/a/main.py",
                    }
                ]
            ),
            ["apps/backend/a"],
        )

    def test_rename_within_component_and_deletion(self):
        self.assertEqual(
            self.check(
                [
                    {
                        "filename": "apps/backend/a/new.py",
                        "status": "renamed",
                        "previous_filename": "apps/backend/a/old.py",
                    },
                    {"filename": "apps/backend/a/deleted.py", "status": "removed"},
                ]
            ),
            ["apps/backend/a"],
        )

    def test_all_pages_are_checked(self):
        first = [{"filename": f"apps/backend/a/file{i}.py"} for i in range(100)]
        second = [{"filename": "apps/backend/b/main.py"}]
        self.assertEqual(
            self.check(first + second, pages=[first, second]),
            ["apps/backend/a", "apps/backend/b"],
        )

    def test_missing_truncated_or_duplicate_file_lists_fail_closed(self):
        for entries, count in (([], 1), ([{"filename": "README.md"}] * 2, 2)):
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                self.check(entries, count=count)

    def test_stale_head_and_malformed_responses_fail_closed(self):
        with self.assertRaises(ValueError):
            self.check([], head="stale")
        for count in (-1, True, "1"):
            with self.subTest(count=count), self.assertRaises(ValueError):
                self.check([], count=count)
        for entry in (
            {},
            {"filename": 2},
            {"filename": ""},
            {"filename": "docs/new.md", "status": "renamed"},
        ):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                self.check([entry])

    def test_cli_exit_status_and_summary(self):
        script = Path(__file__).with_name("check_pr_components.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path, files_path = root / "pr.json", root / "files.json"
            summary_path = root / "summary.md"
            for components, expected in ((["a"], 0), (["a", "b"], 1)):
                report_path.write_text(
                    json.dumps(
                        {
                            "head": {"sha": "current"},
                            "changed_files": len(components),
                        }
                    )
                )
                files_path.write_text(
                    json.dumps(
                        [
                            [
                                {
                                    "filename": f"apps/backend/{name}/main.py",
                                }
                                for name in components
                            ]
                        ]
                    )
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        str(script),
                        str(report_path),
                        str(files_path),
                        "current",
                    ],
                    env={**os.environ, "GITHUB_STEP_SUMMARY": str(summary_path)},
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(
                    result.returncode, expected, result.stdout + result.stderr
                )
                self.assertIn(f"{len(components)} / 1", summary_path.read_text())
                self.assertEqual("::error::" in result.stdout, expected == 1)


if __name__ == "__main__":
    unittest.main()
