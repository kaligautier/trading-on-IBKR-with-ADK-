"""Verify the release image with disposable PostgreSQL and no provider calls."""

import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4


def docker(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout
    )


def require(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout.strip()


def verify(image: str) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "database/scripts"))
    import local_domains

    if local_domains.inspect_container() is None:
        local_domains.reset()
    name = f"scanner-smoke-{uuid4().hex}"
    environment = [
        "-e",
        "DOCKER_ENV=true",
        "-e",
        "MARKET_SCANNER_DATABASE_URL=postgresql://market_scanner_writer:"
        "domain-test-only@127.0.0.1:5432/market_scanner",
        "-e",
        "GOOGLE_CLOUD_PROJECT=offline-test",
        "-e",
        "LITELLM_API_BASE=http://127.0.0.1:9",
        "-e",
        "LITELLM_API_KEY=sk-offline-smoke",
        "-e",
        "DD_TRACE_ENABLED=false",
        "-e",
        "DD_INSTRUMENTATION_TELEMETRY_ENABLED=false",
        "-e",
        "PYTHONPATH=/app/src",
    ]
    try:
        require(
            docker(
                "run",
                "--detach",
                "--name",
                name,
                "--network",
                "container:deepcopy-domains-test",
                *environment,
                image,
            )
        )
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            health = docker(
                "exec",
                name,
                "curl",
                "--fail",
                "--silent",
                "--max-time",
                "2",
                "http://127.0.0.1:8000/health",
            )
            if health.returncode == 0:
                break
            if (
                require(docker("inspect", "--format={{.State.Running}}", name))
                != "true"
            ):
                raise RuntimeError("Server exited: " + require(docker("logs", name)))
            time.sleep(1)
        else:
            raise RuntimeError(
                "Server did not become healthy: " + require(docker("logs", name))
            )

        require(
            docker(
                "exec",
                name,
                "python",
                "-c",
                """
import os
from pathlib import Path
from app.config.llm import create_model
from app.config.settings import settings
from app.components.agents.market_scanner import root_agent
assert os.getuid() != 0, 'Runtime must be non-root'
assert not Path('/app/src/test').exists(), 'Test fixtures must not ship'
assert not list(Path('/app').rglob('.env*')), 'Environment files must not ship'
assert not list(Path('/app').rglob('gha-creds-*.json')), 'Credentials must not ship'
model = create_model(settings)
assert model.client_kwargs['vertexai'] is False
assert model.client_kwargs['enterprise'] is False
assert root_agent is not None
""",
            )
        )
        session_path = f"/apps/market_scanner/users/smoke/sessions/{name}"
        require(
            docker(
                "exec",
                name,
                "curl",
                "--fail",
                "--silent",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "-d",
                '{"proof":42}',
                "http://127.0.0.1:8000" + session_path,
            )
        )
        require(docker("restart", name))
        for _ in range(60):
            response = docker(
                "exec",
                name,
                "curl",
                "--fail",
                "--silent",
                "--max-time",
                "2",
                "http://127.0.0.1:8000" + session_path,
            )
            if response.returncode == 0:
                import json

                assert json.loads(response.stdout)["state"]["proof"] == 42
                break
            time.sleep(1)
        else:
            raise RuntimeError("Session was not readable after process restart")
        worker = docker(
            "exec",
            name,
            "env",
            "-u",
            "MARKET_SCANNER_DATABASE_URL",
            "python",
            "-m",
            "app.jobs.daily_scan",
        )
        if (
            worker.returncode != 1
            or "scheduled_scan.failed" not in worker.stdout + worker.stderr
        ):
            raise RuntimeError(
                "Unconfigured worker must fail without reporting success"
            )
        missing_key = docker(
            "exec",
            name,
            "env",
            "-u",
            "LITELLM_API_KEY",
            "python",
            "-c",
            "import app.config.settings",
        )
        if (
            missing_key.returncode == 0
            or "ConfigurationError" not in missing_key.stderr
        ):
            raise RuntimeError("Missing gateway key must fail at startup")
        print(
            "PASS: PostgreSQL startup and restart, non-root runtime, packaged graph, "
            "worker failure and required key"
        )
    finally:
        docker("rm", "--force", name)


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1].startswith("-"):
        raise SystemExit("Usage: python3 scripts/scanner_image_smoke.py IMAGE")
    verify(sys.argv[1])
