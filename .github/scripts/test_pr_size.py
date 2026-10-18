import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from check_pr_size import line_counts


class SizeTests(unittest.TestCase):
    def counts(self, files, **report_overrides):
        report = {
            "head": {"sha": "current"},
            "changed_files": len(files),
            **report_overrides,
        }
        return line_counts(report, [files], "current")

    def test_excludes_only_known_lockfiles_at_any_depth(self):
        files = [
            {"filename": path, "additions": 7000, "deletions": 2000}
            for path in ("apps/frontend/package-lock.json", "uv.lock")
        ] + [{"filename": "app.py", "additions": 12, "deletions": 3}]
        self.assertEqual(self.counts(files), (12, 3, 2))

    def test_similarly_named_files_and_generated_code_still_count(self):
        for path in ("package-lock.json.md", "docs/lockfile.md", "schema.generated.ts"):
            with self.subTest(path=path):
                self.assertEqual(
                    self.counts(
                        [{"filename": path, "additions": 900, "deletions": 200}]
                    ),
                    (900, 200, 0),
                )

    def test_renaming_source_to_lockfile_does_not_hide_changes(self):
        self.assertEqual(
            self.counts(
                [
                    {
                        "filename": "package-lock.json",
                        "previous_filename": "app.py",
                        "status": "renamed",
                        "additions": 12,
                        "deletions": 4,
                    }
                ]
            ),
            (12, 4, 0),
        )

    def test_lockfile_moves_and_deletions_are_excluded(self):
        self.assertEqual(
            self.counts(
                [
                    {
                        "filename": "apps/frontend/package-lock.json",
                        "previous_filename": "package-lock.json",
                        "status": "renamed",
                        "additions": 1,
                        "deletions": 1,
                    },
                    {
                        "filename": "uv.lock",
                        "status": "removed",
                        "additions": 0,
                        "deletions": 2000,
                    },
                ]
            ),
            (0, 0, 2),
        )

    def test_invalid_counts_fail_even_for_excluded_lockfiles(self):
        for value in (-1, True, "4", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.counts(
                    [{"filename": "uv.lock", "additions": value, "deletions": 0}]
                )

    def test_stale_or_incomplete_listing_is_rejected(self):
        with self.assertRaises(ValueError):
            self.counts([], head={"sha": "stale"})
        with self.assertRaises(ValueError):
            self.counts([], changed_files=100)

    def test_all_pages_contribute_to_size(self):
        files = [
            {"filename": "a.py", "additions": 800, "deletions": 0},
            {"filename": "b.py", "additions": 201, "deletions": 0},
        ]
        self.assertEqual(
            line_counts(
                {"head": {"sha": "current"}, "changed_files": 2},
                [[files[0]], [files[1]]],
                "current",
            ),
            (1001, 0, 0),
        )

    def test_cli_boundary_and_summary(self):
        script = Path(__file__).with_name("check_pr_size.py")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path, files_path, summary_path = [
                root / name for name in ("pr.json", "files.json", "summary.md")
            ]
            for count, expected in ((999, 0), (1000, 0), (1001, 1)):
                report_path.write_text(
                    json.dumps({"head": {"sha": "current"}, "changed_files": 2})
                )
                files_path.write_text(
                    json.dumps(
                        [
                            [
                                {
                                    "filename": "app.py",
                                    "additions": count - 1,
                                    "deletions": 1,
                                },
                                {
                                    "filename": "package-lock.json",
                                    "additions": 6819,
                                    "deletions": 0,
                                },
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
                self.assertIn(f"{count} / 1000", summary_path.read_text())
                self.assertIn("Excluded 1", summary_path.read_text())


if __name__ == "__main__":
    unittest.main()
