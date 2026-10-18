"""Enforce one application component per PR using GitHub's paginated file list."""

import json
import os
import sys
from pathlib import Path, PurePosixPath


def component_for(path: str) -> str | None:
    parts = PurePosixPath(path).parts
    if parts[:2] == ("apps", "backend"):
        return "/".join(parts[:3]) if len(parts) >= 4 else None
    if len(parts) >= 3 and parts[0] == "apps":
        return "/".join(parts[:2])
    return None


def changed_components(report: dict, pages: list, expected_head: str) -> list[str]:
    if not expected_head or report.get("head", {}).get("sha") != expected_head:
        raise ValueError("PR head changed; the latest run must validate its scope.")
    count = report.get("changed_files")
    if type(count) is not int or count < 0:
        raise ValueError("GitHub did not return a valid changed-file count.")
    if not isinstance(pages, list) or any(not isinstance(page, list) for page in pages):
        raise ValueError("GitHub did not return paginated PR files.")
    files = [entry for page in pages for entry in page]
    if len(files) != count:
        raise ValueError("Incomplete PR file list; scope cannot be verified.")

    components = set()
    seen = set()
    for entry in files:
        if not isinstance(entry, dict) or not isinstance(entry.get("filename"), str):
            raise ValueError("GitHub returned an invalid PR file.")
        name = entry["filename"]
        if not name or name in seen:
            raise ValueError("GitHub returned an empty or duplicate PR filename.")
        seen.add(name)
        paths = [name]
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
