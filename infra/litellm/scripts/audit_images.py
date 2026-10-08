"""Audit installed Python packages in the digest-pinned release images.

Requires Docker and uv. No cloud credentials, dependency resolution, installation
inside images or advisory exceptions are used. Any known vulnerability fails.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess


INVENTORY = """
import importlib.metadata as metadata
print("\\n".join(sorted(
    item.metadata["Name"] + "==" + item.version
    for item in metadata.distributions()
)))
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--platform", default="linux/amd64", choices=["linux/amd64", "linux/arm64"]
    )
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    variables = (Path(__file__).resolve().parents[1] / "variables.tf").read_text()
    failed = False
    for variable, name in [
        ("proxy_digest", "litellm"),
        ("migrations_digest", "litellm-migrations"),
    ]:
        block = variables.split(f'variable "{variable}"', 1)[1]
        digest = re.search(r'default\s*=\s*"(sha256:[0-9a-f]{64})"', block)[1]
        image = f"ghcr.io/berriai/{name}@{digest}"
        requirements = args.output_dir / f"{name}-requirements.txt"
        (args.output_dir / f"{name}-image.txt").write_text(
            image + "\n" + args.platform + "\n"
        )
        with requirements.open("w") as output:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--platform=" + args.platform,
                    "--network=none",
                    "--entrypoint=python",
                    image,
                    "-c",
                    INVENTORY,
                ],
                stdout=output,
                check=True,
            )
        print("Auditing installed packages:", image, args.platform, flush=True)
        report = args.output_dir / f"{name}-audit.json"
        result = subprocess.run(
            [
                "uvx",
                "--from",
                "pip-audit==2.10.1",
                "pip-audit",
                "--no-deps",
                "--disable-pip",
                "--progress-spinner",
                "off",
                "-r",
                str(requirements),
                "--format=json",
                "--output",
                str(report),
            ]
        )
        failed = failed or result.returncode != 0
        if report.exists():
            for package in json.loads(report.read_text())["dependencies"]:
                for advisory in package.get("vulns", []):
                    print(
                        package["name"],
                        package["version"],
                        advisory["id"],
                        "fixed in:",
                        ", ".join(advisory["fix_versions"]) or "unavailable",
                    )
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
