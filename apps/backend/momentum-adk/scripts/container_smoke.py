"""Offline production-image checks, run as the image user with networking disabled."""

import os
import subprocess
import sys

from app.config.llm import create_model
from app.config.rate_limit import ModelRequestGate
from app.config.settings import Settings
from app.config.storage import MomentumStorage
from app.services.runtime import MomentumRuntimeFactory

assert os.getuid() == 10001
storage = MomentumStorage.from_environment()
for directory in (
    storage.cache_directory,
    storage.results_directory,
):
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / "smoke"
    probe.write_text("writable")
    probe.unlink()
config = Settings(
    LITELLM_API_BASE="https://gateway.invalid", LITELLM_API_KEY="synthetic"
)
gate = ModelRequestGate()
models = [create_model(config, name, gate) for name in ("quick", "deep")]
app = MomentumRuntimeFactory(
    *models, "postgresql://synthetic@localhost/momentum"
).application()
assert app.name == "momentum"
# Exercise the actual entrypoint and sanitized failure contract without credentials.
env = {**os.environ, "TA_ANALYSIS_REQUEST": "private-marker"}
result = subprocess.run(
    [sys.executable, "-m", "app.job_runner"], env=env, capture_output=True, text=True
)
assert result.returncode == 1
assert "momentum_failed" in result.stdout and "private-marker" not in result.stdout
print(
    "production image: non-root, writable storage, graph import and entrypoint passed"
)
