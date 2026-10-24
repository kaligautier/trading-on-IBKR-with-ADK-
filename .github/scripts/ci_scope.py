"""Select component workflows from the complete PR diff, including deleted paths."""

from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
COMPONENTS = json.loads((ROOT / ".github/ci-components.json").read_text())
SHARED = (
    ".github/ci-components.json",
    ".github/workflows/ci.yml",
    ".github/scripts/ci_*.py",
    ".github/scripts/test_ci_*.py",
    "ruff.toml",
    ".ruff.toml",
    "pyproject.toml",
)


def select(paths: list[str], *, full: bool = False) -> dict[str, bool]:
    full = full or any(fnmatchcase(path, rule) for path in paths for rule in SHARED)
    return {
        name: full
        or any(fnmatchcase(path, rule) for path in paths for rule in component["paths"])
        for name, component in COMPONENTS.items()
    }


def changed_paths(base: str, head: str) -> list[str]:
    if not base or not head:
        raise ValueError("Both PR commit SHAs are required")
    output = subprocess.check_output(
        ["git", "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}"],
        cwd=ROOT,
    )
    return [path.decode("utf-8") for path in output.split(b"\0") if path]


def main() -> None:
    event = os.environ["EVENT_NAME"]
    if event not in {"pull_request", "workflow_dispatch"}:
        raise ValueError(f"Unexpected CI event: {event}")
    full = event == "workflow_dispatch"
    paths = (
        [] if full else changed_paths(os.environ["BASE_SHA"], os.environ["HEAD_SHA"])
    )
    selected = select(paths, full=full)
    print(json.dumps(selected, indent=2))
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:
        output.write(f"selected={json.dumps(selected)}\n")


if __name__ == "__main__":
    main()
