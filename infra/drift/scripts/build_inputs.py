"""Print the private plan inputs as the JSON map the nightly drift workflow reads.

Usage (from the repository root, nothing is printed to the terminal):
  python3 infra/drift/scripts/build_inputs.py | \
    gcloud secrets versions add infra-drift-inputs --data-file=- --project=PROJECT
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Ignored plan inputs, relative to each root directory.
NAMES = (
    "config/identities.local.tfvars",
    "config/sso.local.tfvars",
    "config/agent-governance.local.tfvars.json",
    "config/key-alert.local.tfvars",
    "budget.local.tfvars",
    "billing.local.tfvars",
)


def main() -> int:
    inputs: dict[str, dict[str, str]] = {}
    for directory in sorted(ROOT.glob("*")) + sorted(ROOT.glob("*/*")):
        files = {
            name: (directory / name).read_text()
            for name in NAMES
            if (directory / name).is_file()
        }
        if files:
            inputs[str(directory.relative_to(ROOT))] = files
    if not inputs:
        print("No local plan inputs found.", file=sys.stderr)
        return 1
    json.dump(inputs, sys.stdout, sort_keys=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
