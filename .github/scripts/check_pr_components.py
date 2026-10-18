"""Enforce one application component per PR using GitHub's paginated file list."""

import json
import os
import sys
from pathlib import Path, PurePosixPath

from pr_files import changed_files


def component_for(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    if parts[:2] == ("apps", "backend"):
        return "/".join(parts[:3]) if len(parts) >= 4 else None
    if len(parts) >= 3 and parts[0] == "apps":
        return "/".join(parts[:2])
    return None


def changed_components(report: dict, pages: list, expected_head: str) -> list[str]:
    components = set()
    for entry in changed_files(report, pages, expected_head):
        paths = [entry["filename"]]
        if entry.get("status") == "renamed":
            previous = entry.get("previous_filename")
            if not isinstance(previous, str) or not previous:
                raise ValueError(
                    "Renamed file has no previous path; scope cannot be verified."
                )
            paths.append(previous)
        for path in paths:
            component = component_for(path)
            if component is not None:
                components.add(component)
    return sorted(components)


def main() -> int:
    try:
        report = json.loads(Path(sys.argv[1]).read_text())
        pages = json.loads(Path(sys.argv[2]).read_text())
        components = changed_components(report, pages, sys.argv[3])
    except (ValueError, TypeError, AttributeError, OSError, IndexError) as error:
        print(f"::error::{error}")
        return 1

    summary = (
        f"### PR component scope: {len(components)} / 1\n\n"
        f"Components: {json.dumps(components)}\n\n"
        "Shared files outside component directories do not count. "
        "Renames count both the old and new component.\n"
    )
    print(summary)
    if summary_path := os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(summary_path).write_text(summary)
    if len(components) > 1:
        print(
            "::error::A PR may modify at most one application component. Split this PR."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
