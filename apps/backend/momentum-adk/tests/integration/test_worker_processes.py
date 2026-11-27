"""Independent Momentum worker processes against real PostgreSQL servers started by CI.

- Admission: WORKER_ADMISSION_TEST_URL, the results writer login with
  CONNECTION LIMIT 2 on a server with max_connections=15. A competing process is
  busy, then recovers after a normal end or a crash.
- TLS: WORKER_TLS_TEST_URL (host `localhost`, sslmode=verify-full, no sslrootcert),
  WORKER_TLS_TEST_CA and WORKER_TLS_UNTRUSTED_CA. Both engines verify the server.
"""

import os
import select
import subprocess
import sys
from pathlib import Path

import pytest

APPLICATION = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).with_name("worker_probe.py")


def launch(step: str, mode: str, url: str, **extra: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, str(PROBE), step, mode],
        cwd=APPLICATION,
        env={
            **os.environ,
            "PYTHONPATH": str(APPLICATION),
            "PROBE_URL": url,
            **extra,
        },
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def first_line(process: subprocess.Popen[str]) -> str:
    assert select.select([process.stdout], [], [], 20)[0], "Admission did not finish"
    line = process.stdout.readline().strip()
    if not line:
        _, errors = process.communicate(timeout=5)
        pytest.fail(errors)
    return line


@pytest.fixture
def admission_url() -> str:
    url = os.getenv("WORKER_ADMISSION_TEST_URL")
    if not url:
        pytest.skip("Set WORKER_ADMISSION_TEST_URL to a disposable PostgreSQL")
    return url


@pytest.mark.parametrize("ending", ["normal", "crash"])
def test_competing_process_is_busy_then_recovers(admission_url, ending):
    owner = launch("admission", "hold", admission_url)
    try:
        assert first_line(owner) == "acquired"
        contender = launch("admission", "write", admission_url)
        output, errors = contender.communicate(timeout=20)
        assert contender.returncode == 75, errors
        assert output.strip() == "busy"
        if ending == "crash":
            owner.kill()
        else:
            owner.stdin.write("done\n")
            owner.stdin.flush()
        owner.communicate(timeout=20)
        successor = launch("admission", "cancel", admission_url)
        output, errors = successor.communicate(timeout=20)
        assert successor.returncode == 0, errors
        assert output.splitlines() == ["acquired", "cancelled"]
        final = launch("admission", "write", admission_url)
        output, errors = final.communicate(timeout=20)
        assert final.returncode == 0, errors
        assert output.strip() == "acquired"
    finally:
        if owner.poll() is None:
            owner.kill()
        owner.communicate(timeout=20)


@pytest.mark.parametrize("kind", ["result", "session"])
@pytest.mark.parametrize("case", ["trusted", "wrong_ca", "wrong_hostname"])
def test_worker_engines_verify_tls(kind, case):
    url, trusted, untrusted = (
        os.getenv(name)
        for name in (
            "WORKER_TLS_TEST_URL",
            "WORKER_TLS_TEST_CA",
            "WORKER_TLS_UNTRUSTED_CA",
        )
    )
    if not (url and trusted and untrusted):
        pytest.skip(
            "Set WORKER_TLS_TEST_URL, WORKER_TLS_TEST_CA and WORKER_TLS_UNTRUSTED_CA"
        )
    ca = untrusted if case == "wrong_ca" else trusted
    if case == "wrong_hostname":
        url = url.replace("@localhost:", "@127.0.0.1:")
    address = f"{url}&sslrootcert={ca}"
    result = subprocess.run(
        [sys.executable, str(PROBE), "tls", kind],
        cwd=APPLICATION,
        env={
            **os.environ,
            "PYTHONPATH": str(APPLICATION),
            "PROBE_URL": address,
            "DATABASE_CA_FILE": ca,
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    password = address.split(":", 2)[2].split("@", 1)[0]
    assert password not in result.stdout + result.stderr
    if case == "trusted":
        assert result.returncode == 0, result.stdout + result.stderr
        assert "verified TLS" in result.stdout
    else:
        assert result.returncode == 1, result.stdout + result.stderr
        assert "SSLCertVerificationError" in result.stdout
