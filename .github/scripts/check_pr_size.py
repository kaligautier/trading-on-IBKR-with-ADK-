"""Limit reviewable PR lines while retaining generated lockfiles in Git."""

import json
import os
import sys
from pathlib import Path, PurePosixPath

from pr_files import changed_files

LIMIT = 1000
LOCKFILES = {"package-lock.json", "uv.lock"}


def line_counts(report: dict, pages: list, expected_head: str) -> tuple[int, int, int]:
    additions = deletions = ignored = 0
    for entry in changed_files(report, pages, expected_head):
        counts = [entry.get("additions"), entry.get("deletions")]
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("GitHub did not return valid PR line counts.")
        lockfile = PurePosixPath(entry["filename"]).name in LOCKFILES
        if entry.get("status") == "renamed":
            previous = entry.get("previous_filename")
            if not isinstance(previous, str) or not previous:
                raise ValueError("Renamed file has no previous path.")
            # Renaming source code to a lockfile must not hide its changes.
            lockfile = lockfile and PurePosixPath(previous).name in LOCKFILES
        if lockfile:
            ignored += 1
        else:
            additions += counts[0]
            deletions += counts[1]
    return additions, deletions, ignored


def main() -> int:
    try:
        report = json.loads(Path(sys.argv[1]).read_text())
        pages = json.loads(Path(sys.argv[2]).read_text())
        additions, deletions, ignored = line_counts(report, pages, sys.argv[3])
    except (ValueError, TypeError, AttributeError, OSError, IndexError) as error:
        print(f"::error::{error}")
        return 1
    total = additions + deletions
    summary = (
        f"### PR size: {total} / {LIMIT} lines\n\n"
        f"{additions} additions + {deletions} deletions. "
        f"Excluded {ignored} generated lockfile(s): package-lock.json and uv.lock.\n"
    )
    print(summary)
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(summary_path).write_text(summary)
    if total > LIMIT:
        print(
            "::error::PR exceeds 1,000 counted lines. Split this change into smaller PRs."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
