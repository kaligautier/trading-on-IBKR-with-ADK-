"""Deploy an immutable image with Terraform, then require live MCP verification."""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
VERIFIER = REPOSITORY / "apps/backend/momentum-public-mcp/scripts/verify_live.py"
IMAGE = re.compile(
    r"europe-west1-docker\.pkg\.dev/preprod-deep-copy/market-scanner/"
    r"momentum-public-mcp@sha256:[0-9a-f]{64}\Z"
)


def run(arguments, *, capture=False):
    return subprocess.run(
        arguments, cwd=ROOT, check=True, text=True, capture_output=capture
    ).stdout


def deploy(image, variables, evidence, *, plan_only=False):
    if not IMAGE.fullmatch(image):
        raise ValueError("Use the immutable MCP image digest in preprod-deep-copy")
    content = variables.read_text()
    updated, count = re.subn(
        r'(?m)^image\s*=\s*"[^"\n]+"', f'image = "{image}"', content
    )
    if count != 1:
        raise ValueError("Expected exactly one image assignment in the release tfvars")
    # A prior build identifier no longer describes the replacement image.
    updated = re.sub(r"(?m)^# Cloud Build .*\n", "", updated)
    run(
        [
            "terraform",
            "init",
            "-input=false",
            "-backend-config=config/preprod.backend.hcl",
        ]
    )
    with tempfile.TemporaryDirectory(prefix="mcp-release-") as directory:
        plan = str(Path(directory) / "release.tfplan")
        run(
            [
                "terraform",
                "plan",
                "-input=false",
                f"-var-file={variables}",
                f"-var=image={image}",
                f"-out={plan}",
            ]
        )
        if plan_only:
            return
        run(["terraform", "apply", "-input=false", plan])
    endpoint = run(["terraform", "output", "-raw", "service_url"], capture=True).strip()
    # Deliberately no --suggestion-symbol: deployment verification never writes data.
    verification = json.loads(
        run([sys.executable, str(VERIFIER), endpoint], capture=True)
    )
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(
        json.dumps({"image": image, "verification": verification}, indent=2) + "\n"
    )
    # Record the image only after it has passed the business/transport checks.
    variables.write_text(updated)
    run(["terraform", "fmt", str(variables)])
    print(f"Verified deployment: {endpoint}\nEvidence: {evidence}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="Destination image reference with @sha256 digest")
    parser.add_argument("--var-file", type=Path, default=ROOT / "config/preprod.tfvars")
    parser.add_argument(
        "--evidence", type=Path, default=REPOSITORY / ".local/mcp-release.json"
    )
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    try:
        deploy(
            args.image,
            args.var_file.resolve(),
            args.evidence.resolve(),
            plan_only=args.plan_only,
        )
    except subprocess.CalledProcessError as error:
        # Preserve failed verifier output and a failing exit code for CI/operators.
        if error.stdout:
            print(error.stdout, file=sys.stderr)
        if error.stderr:
            print(error.stderr, file=sys.stderr)
        raise SystemExit(error.returncode) from error


if __name__ == "__main__":
    main()
