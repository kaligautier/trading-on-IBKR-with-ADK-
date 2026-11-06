"""Build the security-patched proxy/migrations from the pinned official bases."""

import argparse
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", default="linux/amd64")
    args = parser.parse_args()
    variables = (ROOT / "variables.tf").read_text()
    for variable, name in [
        ("proxy_digest", "litellm"),
        ("migrations_digest", "litellm-migrations"),
    ]:
        block = variables.split(f'variable "{variable}"', 1)[1]
        digest = re.search(r'default\s*=\s*"(sha256:[0-9a-f]{64})"', block)[1]
        subprocess.run(
            [
                "docker",
                "build",
                "--platform=" + args.platform,
                "--build-arg",
                f"BASE_IMAGE=ghcr.io/berriai/{name}@{digest}",
                "--build-arg",
                "RUNTIME_USER="
                + ("nonroot" if name == "litellm-migrations" else "root"),
                "--tag",
                f"{name}:security-patched",
                str(ROOT / "images"),
            ],
            check=True,
        )


if __name__ == "__main__":
    main()
