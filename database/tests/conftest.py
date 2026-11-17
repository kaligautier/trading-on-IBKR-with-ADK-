"""Only the dedicated, labelled local domain test server may be rebuilt."""

from pathlib import Path
import os
import subprocess
from tempfile import TemporaryDirectory

import pytest


@pytest.fixture
def mounted_changelog():
    # Colima shares the checkout, but not macOS's default pytest temp directory.
    cache = Path(__file__).resolve().parents[2] / ".pytest_cache"
    cache.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=cache) as directory:
        path = Path(directory) / "changelog"
        path.mkdir(mode=0o755)
        yield path


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
