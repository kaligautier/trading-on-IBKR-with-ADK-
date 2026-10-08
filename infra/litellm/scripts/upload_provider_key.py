"""Upload a provider key from a hidden terminal prompt; never print its value."""

import argparse
import getpass
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=["openai", "anthropic", "gemini"])
    parser.add_argument("--project", required=True)
    parser.add_argument("--account", required=True)
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error(
            "Run in an interactive terminal; keys are accepted only by hidden prompt."
        )
    key = getpass.getpass(f"{args.provider} API key (hidden): ").strip()
    if not key or any(char.isspace() for char in key):
        parser.error("The API key must be nonempty and contain no whitespace.")
    result = subprocess.run(
        [
            "gcloud",
            "secrets",
            "versions",
            "add",
            f"litellm-provider-{args.provider}",
            f"--project={args.project}",
            f"--account={args.account}",
            "--data-file=-",
            "--format=value(name)",
        ],
        input=key,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        # Do not expose command output that could include credential material.
        raise SystemExit(
            "Upload failed. Check the selected account and secret permissions."
        )
    version = result.stdout.strip().rsplit("/", 1)[-1]
    if not version.isdecimal():
        raise SystemExit(
            "Upload completed but its version could not be parsed; check Secret Manager."
        )
    print(f"Uploaded litellm-provider-{args.provider}, version {version}.")
    print(
        f'Pin {args.provider} = "{version}" in provider_secret_versions, then plan and deploy.'
    )


if __name__ == "__main__":
    main()
