"""Deterministic offline OpenAPI export; never connects to storage or reads secrets."""

import argparse
import json
from pathlib import Path

from app.application import create_app
from app.config import Settings

TARGET = Path(__file__).resolve().parents[1] / "openapi.json"


def export() -> str:
    settings = Settings(
        DATABASE_URL="postgresql://momentum_results_reader:unused@localhost/momentum",
        API_TOKEN="offline-contract-placeholder",  # noqa: S106 -- offline export only
        AUTH_MODE="token",
        DATABASE_POOL_SIZE=1,
        DATABASE_POOL_TIMEOUT=5,
        _env_file=None,
    )
    return json.dumps(create_app(settings).openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = export()
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != content:
            raise SystemExit("OpenAPI drift: run python scripts/export_openapi.py")
        print("OpenAPI export matches the executable contract.")
    else:
        TARGET.write_text(content)
