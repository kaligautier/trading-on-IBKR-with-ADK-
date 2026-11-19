"""Helpers of the deploy workflow.

release.py config ROOT       print the root's release settings as key=value lines
release.py record FILE DIGEST  pin DIGEST (sha256:...) on the single `image = "...@sha256:..."` line
"""

import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
KEYS = ("app", "image", "prefix", "release_file")
IMAGE_LINE = re.compile(r'^(image\s*=\s*"[^"@]+@)sha256:[0-9a-f]{64}(")', re.MULTILINE)
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def load(root):
    releases = json.loads((HERE.parent / "releases.json").read_text())
    if root not in releases:
        raise SystemExit(
            f"Unknown root {root!r}; use one of {', '.join(sorted(releases))}"
        )
    return releases[root]


def config_lines(root):
    release = load(root)
    lines = [f"{key}={release[key]}" for key in KEYS]
    lines.append("plan_vars=" + " ".join(release["plan_vars"]))
    return lines


def record(path, digest):
    if not DIGEST.match(digest):
        raise SystemExit("Use a sha256:... digest")
    target = pathlib.Path(path)
    text = target.read_text()
    updated, count = IMAGE_LINE.subn(
        lambda match: f"{match.group(1)}{digest}{match.group(2)}", text
    )
    if count != 1:
        raise SystemExit(
            f"Expected exactly one pinned image line in {path}, found {count}"
        )
    target.write_text(updated)


def main(argv):
    if len(argv) == 3 and argv[1] == "config":
        lines = config_lines(argv[2])
        print("\n".join(lines))
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output, "a") as handle:
                handle.write("\n".join(lines) + "\n")
        return 0
    if len(argv) == 4 and argv[1] == "record":
        record(argv[2], argv[3])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
