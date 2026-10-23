"""Only the dedicated, labelled local domain test server may be rebuilt."""

from pathlib import Path
import os
import subprocess

import pytest


@pytest.fixture(scope="session", autouse=True)
def local_transport():
    previous = os.environ.get("PGSSLMODE")
    os.environ["PGSSLMODE"] = "disable"
    yield
    if previous is None:
        os.environ.pop("PGSSLMODE", None)
    else:
        os.environ["PGSSLMODE"] = previous


@pytest.fixture(scope="session")
def domain_databases(local_transport):
    script = Path(__file__).resolve().parents[1] / "testing/local_domains.py"
    subprocess.run(["python3", str(script), "reset"], check=True)
